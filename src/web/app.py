from pathlib import Path
import os
import secrets
import logging
import random
import json
import re
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, abort, after_this_request, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_wtf.csrf import CSRFProtect
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.exceptions import HTTPException

from .auth import login_manager, verify_credentials, User
from .security import validate_filename, validate_email, is_safe_url
from .dashboard_service import (
    apply_manual_review,
    categorize_notices,
    filter_summaries,
    filter_records_by_cache_window,
    get_cache_coverage_info,
    get_record_by_file_name,
    get_last_update_time,
    load_dashboard_config,
    load_summaries,
    paginate_summaries,
    run_manual_monitoring,
    save_dashboard_config,
    sort_summaries,
    summarize_metrics,
)
from src.utils.dou_url_utils import (
    is_invalid_year_number_slug,
    rebuild_legacy_slug,
)

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARIES_DIR = BASE_DIR / "data" / "summaries"
DEFAULT_CONFIG_PATH = BASE_DIR / "data" / "dashboard_config.json"


def _parse_positive_int(raw_value: str, default: int) -> int:
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return default


def create_app(summaries_dir: Path | None = None, config_path: Path | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SERVER_BOOT_ID"] = secrets.token_hex(16)
    
    # 🔒 SECURITY FIX: Use environment variable for SECRET_KEY
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_urlsafe(32)
    
    # ⏰ SESSION: Configure session timeout (default: 30 minutes of inactivity)
    session_timeout_minutes = int(os.environ.get("SESSION_TIMEOUT_MINUTES", 30))
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=session_timeout_minutes)
    
    # 🔒 SECURITY: Initialize CSRF protection
    csrf = CSRFProtect(app)
    
    # 🔒 SECURITY: Initialize authentication
    login_manager.init_app(app)
    
    # 🔒 SECURITY: Configure logging
    if not app.debug:
        logs_dir = BASE_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        file_handler = RotatingFileHandler(
            logs_dir / "security.log",
            maxBytes=10240000,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('DOU Monitor startup')
    
    # 🔒 SECURITY: Add security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    active_summaries_dir = summaries_dir or DEFAULT_SUMMARIES_DIR
    active_config_path = config_path or DEFAULT_CONFIG_PATH

    # Brute-force protection (in-memory): CAPTCHA after X failures and progressive lockout.
    CAPTCHA_AFTER_FAILURES = 3
    LOCKOUT_AFTER_FAILURES = 5
    ATTEMPT_WINDOW = timedelta(minutes=15)
    BASE_LOCKOUT_MINUTES = 5
    MAX_LOCKOUT_MINUTES = 120
    failed_attempts_by_ip: dict[str, list[datetime]] = {}
    lockout_until_by_ip: dict[str, datetime] = {}
    lockout_level_by_ip: dict[str, int] = {}

    def _client_ip() -> str:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.remote_addr or "unknown"

    def _prune_attempts(ip: str, now: datetime) -> None:
        attempts = failed_attempts_by_ip.get(ip, [])
        cutoff = now - ATTEMPT_WINDOW
        filtered = [ts for ts in attempts if ts >= cutoff]
        if filtered:
            failed_attempts_by_ip[ip] = filtered
        else:
            failed_attempts_by_ip.pop(ip, None)

    def _recent_failures(ip: str, now: datetime) -> int:
        _prune_attempts(ip, now)
        return len(failed_attempts_by_ip.get(ip, []))

    def _current_lockout_until(ip: str, now: datetime) -> datetime | None:
        lockout_until = lockout_until_by_ip.get(ip)
        if lockout_until and lockout_until > now:
            return lockout_until
        lockout_until_by_ip.pop(ip, None)
        return None

    def _register_failure(ip: str, now: datetime) -> int:
        _prune_attempts(ip, now)
        attempts = failed_attempts_by_ip.setdefault(ip, [])
        attempts.append(now)
        current_count = len(attempts)
        if current_count >= LOCKOUT_AFTER_FAILURES:
            level = lockout_level_by_ip.get(ip, 0) + 1
            lockout_level_by_ip[ip] = level
            lock_minutes = min(BASE_LOCKOUT_MINUTES * (2 ** (level - 1)), MAX_LOCKOUT_MINUTES)
            lockout_until_by_ip[ip] = now + timedelta(minutes=lock_minutes)
            # Clear rolling attempt window after lock starts so next cycle is explicit.
            failed_attempts_by_ip.pop(ip, None)
        return current_count

    def _clear_failures(ip: str) -> None:
        failed_attempts_by_ip.pop(ip, None)
        lockout_until_by_ip.pop(ip, None)
        lockout_level_by_ip.pop(ip, None)

    def _ensure_captcha_challenge() -> str:
        prompt = session.get("login_captcha_prompt")
        answer = session.get("login_captcha_answer")
        if prompt and answer is not None:
            return str(prompt)

        left = random.randint(1, 9)
        right = random.randint(1, 9)
        prompt = f"Quanto é {left} + {right}?"
        session["login_captcha_prompt"] = prompt
        session["login_captcha_answer"] = str(left + right)
        return prompt

    def _clear_captcha_challenge() -> None:
        session.pop("login_captcha_prompt", None)
        session.pop("login_captcha_answer", None)

    @app.context_processor
    def utility_processor():
        def url_with_updates(**updates):
            current = request.args.to_dict(flat=True)
            for key, value in updates.items():
                current[key] = str(value)
            return url_for("index", **current)

        return {"url_with_updates": url_with_updates}

    @app.before_request
    def enforce_reauth_after_server_restart():
        """Invalidate authenticated sessions created before current server boot."""
        if not current_user.is_authenticated:
            return None

        expected_boot_id = app.config.get("SERVER_BOOT_ID")
        active_boot_id = session.get("session_boot_id")
        if active_boot_id == expected_boot_id:
            return None

        app.logger.info(f"Session invalidated after restart: user={current_user.id} ip={request.remote_addr}")
        logout_user()
        session.clear()
        flash("Sua sessão expirou após reinicialização do servidor. Faça login novamente.", "warning")
        return redirect(url_for("login"))
    
    # 🔒 SECURITY: Authentication routes
    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Login page"""
        if current_user.is_authenticated:
            return redirect(url_for("index"))

        ip = _client_ip()
        now = datetime.utcnow()
        lockout_until = _current_lockout_until(ip, now)

        def _render_login() -> str:
            current_now = datetime.utcnow()
            current_lockout = _current_lockout_until(ip, current_now)
            failures = _recent_failures(ip, current_now)
            show_captcha = current_lockout is None and failures >= CAPTCHA_AFTER_FAILURES
            captcha_prompt = _ensure_captcha_challenge() if show_captcha else ""
            if not show_captcha:
                _clear_captcha_challenge()
            return render_template(
                "login.html",
                show_captcha=show_captcha,
                captcha_prompt=captcha_prompt,
            )
        
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if lockout_until:
                minutes_left = max(1, int((lockout_until - now).total_seconds() // 60) + 1)
                app.logger.warning(f"Login blocked (lockout): ip={ip} user={username}")
                flash(f"Muitas tentativas falhas. Tente novamente em {minutes_left} minuto(s).", "error")
                return _render_login()

            failures = _recent_failures(ip, now)
            captcha_required = failures >= CAPTCHA_AFTER_FAILURES
            if captcha_required:
                captcha_answer = request.form.get("captcha_answer", "").strip()
                expected_answer = str(session.get("login_captcha_answer", ""))
                if not expected_answer or captcha_answer != expected_answer:
                    current_count = _register_failure(ip, now)
                    app.logger.warning(f"Login captcha failed: ip={ip} user={username} failures={current_count}")
                    flash("CAPTCHA inválido. Tente novamente.", "error")
                    _clear_captcha_challenge()
                    return _render_login()
            
            if verify_credentials(username, password):
                user = User(username)
                login_user(user, remember=False)
                
                # Mark session as permanent to use PERMANENT_SESSION_LIFETIME (30min default)
                session.permanent = True
                session["session_boot_id"] = app.config.get("SERVER_BOOT_ID")
                
                app.logger.info(f"Login successful: user={username} ip={request.remote_addr}")
                _clear_failures(ip)
                _clear_captcha_challenge()
                
                next_page = request.args.get("next")
                if next_page and next_page.startswith("/"):
                    return redirect(next_page)
                return redirect(url_for("index"))
            else:
                current_count = _register_failure(ip, now)
                app.logger.warning(f"Login failed: user={username} ip={request.remote_addr} failures={current_count}")
                if current_count >= LOCKOUT_AFTER_FAILURES:
                    active_lockout = _current_lockout_until(ip, datetime.utcnow())
                    if active_lockout:
                        minutes_left = max(1, int((active_lockout - datetime.utcnow()).total_seconds() // 60) + 1)
                        flash(f"Muitas tentativas falhas. Acesso bloqueado por {minutes_left} minuto(s).", "error")
                    else:
                        flash("Muitas tentativas falhas. Acesso bloqueado temporariamente.", "error")
                elif current_count >= CAPTCHA_AFTER_FAILURES:
                    flash("Usuário ou senha inválidos. CAPTCHA exigido após múltiplas tentativas.", "error")
                else:
                    flash("Usuário ou senha inválidos", "error")
        
        return _render_login()

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        """Password recovery placeholder route (email flow to be implemented)."""
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            app.logger.info(f"Password recovery placeholder requested: email={email or '<empty>'} ip={request.remote_addr}")
            flash(
                "Se o email estiver cadastrado, você receberá instruções para redefinir a senha. "
                "(Placeholder: envio de email ainda não implementado)",
                "success",
            )
            return redirect(url_for("forgot_password"))

        return render_template("forgot_password.html")
    
    @app.route("/logout")
    @login_required
    def logout():
        """Logout endpoint"""
        username = current_user.id
        logout_user()
        session.clear()
        app.logger.info(f"Logout: user={username}")
        flash("Você saiu do sistema", "success")
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def index():
        records = load_summaries(active_summaries_dir)
        config = load_dashboard_config(active_config_path)
        
        # Quick filters
        inscricoes_abertas = request.args.get("inscricoes_abertas") == "1"
        provas_proximas = request.args.get("provas_proximas") == "1"
        revisados = request.args.get("revisados") == "1"
        
        filters = {
            "q": request.args.get("q", ""),
            "orgao": request.args.get("orgao", ""),
            "cargo": request.args.get("cargo", ""),
            "banca": request.args.get("banca", ""),
            "inscricao_to": request.args.get("inscricao_to", ""),
        }
        
        # Apply quick filters
        if inscricoes_abertas:
            from datetime import datetime
            today = datetime.now().date().isoformat()
            records = [r for r in records if r.get("inscricao_inicio") and r.get("inscricao_inicio") <= today and (not r.get("inscricao_fim") or r.get("inscricao_fim") >= today)]
        
        if provas_proximas:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            week_ahead = (today + timedelta(days=7)).isoformat()
            today_iso = today.isoformat()
            records = [r for r in records if r.get("data_prova") and today_iso <= r.get("data_prova") <= week_ahead]
        
        if revisados:
            records = [r for r in records if r.get("is_reviewed")]
        
        sort_by = request.args.get("sort_by", "data_prova")
        sort_dir = request.args.get("sort_dir", "desc")
        page = _parse_positive_int(request.args.get("page", "1"), 1)
        page_size = _parse_positive_int(request.args.get("page_size", "10"), 10)

        # Apply filters first
        filtered = filter_summaries(records, filters)
        
        # Categorize into abertura and outros
        categorized = categorize_notices(filtered)
        abertura_records = categorized["abertura"]
        outros_records = categorized["outros"]
        outros_window_days = config.get("filters", {}).get("default_days", 7)
        outros_filtered = filter_records_by_cache_window(outros_records, outros_window_days)
        outros_window_info = get_cache_coverage_info(records, outros_window_days)

        edit_file = request.args.get("edit", "")
        # Search for edit_record in both abertura and outros (to allow review of all editais)
        edit_record = get_record_by_file_name(abertura_records, edit_file)
        if not edit_record:
            edit_record = get_record_by_file_name(outros_filtered, edit_file)

        cancel_query_params = request.args.to_dict(flat=True)
        cancel_query_params.pop("edit", None)
        cancel_edit_url = url_for("index", **cancel_query_params)
        
        # Sort and paginate abertura (main section)
        sorted_abertura = sort_summaries(abertura_records, sort_by, sort_dir)
        page_items, page_meta = paginate_summaries(sorted_abertura, page, page_size)
        
        # Sort outros (no pagination for now, or show first N)
        sorted_outros = sort_summaries(outros_filtered, sort_by, sort_dir)
        outros_display = sorted_outros[:20]  # Show max 20 outros
        
        # Metrics based on filtered results
        metrics = summarize_metrics(filtered)
        metrics["abertura_count"] = len(abertura_records)
        metrics["outros_count"] = len(outros_filtered)
        
        # Get last update time
        last_update = get_last_update_time(active_summaries_dir)
        
        api_url = url_for("notices_api", **request.args.to_dict(flat=True))
        
        # Load DOU URL configuration for admin UI
        from src.config.dou_urls import get_dou_config
        dou_config = get_dou_config()
        dou_urls = {
            "base_url": dou_config.get_base_url(),
            "search_url": dou_config.get_search_url(),
            "document_url_pattern": dou_config.config.get("document_url_pattern", "")
        }
        dou_health = dou_config.get_health_status()
        dou_health_components = dou_health.get("components", {}) if isinstance(dou_health, dict) else {}
        dou_health_alerts = []
        for component_name, component_health in dou_health_components.items():
            failures = component_health.get("consecutive_failures", 0)
            threshold = component_health.get("alert_threshold", 3)
            if failures >= threshold:
                dou_health_alerts.append(
                    {
                        "component": component_name,
                        "failures": failures,
                        "threshold": threshold,
                        "last_failure": component_health.get("last_failure"),
                    }
                )

        return render_template(
            "dashboard.html",
            records=page_items,
            outros_records=outros_display,
            metrics=metrics,
            filters=filters,
            config=config,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page_meta=page_meta,
            api_url=api_url,
            last_update=last_update,
            outros_window_info=outros_window_info,
            edit_record=edit_record,
            current_query=request.query_string.decode("utf-8"),
            cancel_edit_url=cancel_edit_url,
            dou_urls=dou_urls,
            dou_health=dou_health,
            dou_health_components=dou_health_components,
            dou_health_alerts=dou_health_alerts,
        )

    @app.get("/api/notices")
    @app.get("/api/concursos")
    @login_required
    def notices_api():
        records = load_summaries(active_summaries_dir)
        filters = {
            "q": request.args.get("q", ""),
            "orgao": request.args.get("orgao", ""),
            "cargo": request.args.get("cargo", ""),
            "banca": request.args.get("banca", ""),
            "inscricao_to": request.args.get("inscricao_to", ""),
        }
        sort_by = request.args.get("sort_by", "data_prova")
        sort_dir = request.args.get("sort_dir", "desc")
        page = _parse_positive_int(request.args.get("page", "1"), 1)
        page_size = _parse_positive_int(request.args.get("page_size", "10"), 10)

        filtered = filter_summaries(records, filters)
        sorted_records = sort_summaries(filtered, sort_by, sort_dir)
        items, page_meta = paginate_summaries(sorted_records, page, page_size)

        return jsonify(
            {
                "items": items,
                "metrics": summarize_metrics(filtered),
                "filters": filters,
                "sort": {"by": sort_by, "dir": sort_dir},
                "pagination": page_meta,
            }
        )

    @app.post("/settings/filters")
    @login_required
    def save_filters():
        config = load_dashboard_config(active_config_path)
        keywords_raw = request.form.get("keywords", "")
        days_raw = request.form.get("default_days", "7")

        keywords = [x.strip() for x in keywords_raw.split(",") if x.strip()]
        default_days = _parse_positive_int(days_raw, 7)

        config["filters"]["keywords"] = keywords or config["filters"].get("keywords", [])
        config["filters"]["default_days"] = default_days
        save_dashboard_config(active_config_path, config)
        flash("Configurações de filtros salvas.", "success")
        return redirect(url_for("index"))

    @app.post("/settings/notifications")
    @login_required
    def save_notifications():
        config = load_dashboard_config(active_config_path)

        threshold_raw = request.form.get("threshold", "1")
        email_to = request.form.get("email_to", "").strip()
        webhook_url = request.form.get("webhook_url", "").strip()
        desktop_enabled = request.form.get("desktop_enabled") == "on"
        
        # 🔒 SECURITY: Validate email
        if email_to:
            is_valid, error_msg = validate_email(email_to)
            if not is_valid:
                flash(f"❌ Email inválido: {error_msg}", "error")
                return redirect(url_for("index"))
        
        # 🔒 SECURITY: Validate webhook URL (prevent SSRF)
        if webhook_url:
            is_valid, error_msg = is_safe_url(webhook_url, require_https=True)
            if not is_valid:
                app.logger.warning(f"Blocked unsafe webhook: {webhook_url} - {error_msg} ip={request.remote_addr}")
                flash(f"❌ URL de webhook inválida: {error_msg}", "error")
                return redirect(url_for("index"))

        threshold = _parse_positive_int(threshold_raw, 1)

        config["notifications"]["threshold"] = threshold
        config["notifications"]["email_to"] = email_to
        config["notifications"]["webhook_url"] = webhook_url
        config["notifications"]["desktop_enabled"] = desktop_enabled

        save_dashboard_config(active_config_path, config)
        flash("Configurações de notificação salvas.", "success")
        return redirect(url_for("index"))

    @app.post("/run/manual")
    @login_required
    def run_manual():
        days_raw = request.form.get("days", "7")
        days = _parse_positive_int(days_raw, 7)
        
        # 🔒 SECURITY: Log manual execution
        app.logger.info(f"Manual execution: user={current_user.id} days={days} ip={request.remote_addr}")
        
        # Always use export_pdf=False (PDFs are downloaded on-demand from DOU)
        result = run_manual_monitoring(BASE_DIR, days, export_pdf=False)
        
        if result["success"]:
            msg = f"🔍 Busca concluída: {result['total_concursos']} concursos encontrados "
            msg += f"({result['abertura_concursos']} aberturas, {result['outros_concursos']} outros). "
            msg += f"Summaries extraídos/atualizados: {result['processed']}. "
            msg += "PDFs disponíveis para download on-demand do DOU."
            if result['errors'] > 0:
                msg += f" ⚠️ {result['errors']} erro(s)."
                flash(msg, "warning")
        else:
            flash(f"Erro: {result['error_message']}", "error")
        
        return redirect(url_for("index"))
    
    @app.post("/update-dou-urls")
    @login_required
    def update_dou_urls():
        """Admin function to update DOU URL configuration"""
        base_url = request.form.get("base_url", "").strip()
        search_url = request.form.get("search_url", "").strip()
        document_url_pattern = request.form.get("document_url_pattern", "").strip()
        search_threshold_raw = request.form.get("search_threshold", "").strip()
        processing_threshold_raw = request.form.get("processing_threshold", "").strip()
        pdf_download_threshold_raw = request.form.get("pdf_download_threshold", "").strip()
        
        if not all([base_url, search_url, document_url_pattern]):
            flash("Erro: Todos os campos de URL são obrigatórios", "error")
            return redirect(url_for("index"))
        
        # 🔒 SECURITY: Log URL updates (admin action)
        app.logger.info(f"DOU URLs update requested: user={current_user.id} ip={request.remote_addr}")
        
        from src.config.dou_urls import get_dou_config
        dou_config = get_dou_config()

        def _parse_threshold(raw: str, label: str) -> int | None:
            if raw == "":
                return None
            if not raw.isdigit():
                raise ValueError(f"{label} deve ser um inteiro positivo")
            value = int(raw)
            if value < 1:
                raise ValueError(f"{label} deve ser >= 1")
            return value

        try:
            search_threshold = _parse_threshold(search_threshold_raw, "Limiar de busca")
            processing_threshold = _parse_threshold(processing_threshold_raw, "Limiar de processamento")
            pdf_download_threshold = _parse_threshold(pdf_download_threshold_raw, "Limiar de download PDF")
        except ValueError as e:
            flash(f"❌ {str(e)}", "error")
            return redirect(url_for("index"))
        
        success, message = dou_config.update_urls(
            base_url=base_url,
            search_url=search_url,
            document_url_pattern=document_url_pattern,
            updated_by=current_user.id
        )

        if success:
            success, threshold_message = dou_config.update_alert_thresholds(
                search_threshold=search_threshold,
                processing_threshold=processing_threshold,
                pdf_download_threshold=pdf_download_threshold,
                updated_by=current_user.id,
            )
            if not success:
                message = f"URLs atualizadas, mas houve erro nos limiares: {threshold_message}"
        
        if success:
            app.logger.info(f"DOU URLs updated successfully by user={current_user.id}")
            flash(f"✅ {message}", "success")
        else:
            app.logger.error(f"Failed to update DOU URLs: {message}")
            flash(f"❌ {message}", "error")
        
        return redirect(url_for("index"))

    @app.post("/review/manual")
    @login_required
    def save_manual_review():
        file_name = request.form.get("file_name", "")
        reviewer = request.form.get("reviewer", "dashboard-user")
        next_query = request.form.get("next_query", "")
        
        # 🔒 SECURITY: Log MIT review attempt
        app.logger.info(f"MIT Review: user={current_user.id} file={file_name} reviewer={reviewer} ip={request.remote_addr}")

        updates = {
            "orgao": request.form.get("orgao", ""),
            "edital_numero": request.form.get("edital_numero", ""),
            "cargo": request.form.get("cargo", ""),
            "banca": request.form.get("banca", ""),
            "vagas_total": request.form.get("vagas_total", ""),
            "taxa_inscricao": request.form.get("taxa_inscricao", ""),
            "data_prova": request.form.get("data_prova", ""),
        }

        review_result = apply_manual_review(
            summaries_dir=active_summaries_dir,
            backup_dir=active_summaries_dir.parent / "backups",
            reviewed_examples_dir=active_summaries_dir.parent / "reviewed_examples",
            file_name=file_name,
            updates=updates,
            reviewer=reviewer,
        )

        if review_result["success"]:
            changed = review_result.get("changed_fields", [])
            if changed:
                # Mapeamento de nomes de campos para português
                field_names = {
                    "orgao": "órgão",
                    "edital_numero": "edital",
                    "cargo": "cargo",
                    "banca": "banca",
                    "vagas_total": "vagas",
                    "taxa_inscricao": "taxa",
                    "data_prova": "data da prova"
                }
                fields_list = [field_names.get(f.split(".")[-1], f.split(".")[-1]) for f in changed]
                fields_str = ", ".join(fields_list)
                flash(f"✅ MIT aplicado: {review_result['message']} Campos alterados: {fields_str}", "success")
            else:
                flash(f"ℹ️ {review_result['message']}", "success")
        else:
            flash(f"❌ Erro ao aplicar MIT: {review_result['message']}", "error")

        # Remove edit_id from query string after successful save
        if next_query:
            from urllib.parse import parse_qs, urlencode
            safe_query = next_query.lstrip("?")
            params = parse_qs(safe_query)
            params.pop('edit_id', None)  # Remove edit_id to close review panel
            if params:
                clean_query = urlencode(params, doseq=True)
                return redirect(url_for("index") + f"?{clean_query}")
        return redirect(url_for("index"))

    @app.get("/download-pdf/<summary_id>")
    @login_required
    def download_pdf_from_dou(summary_id):
        """Download PDF from DOU on-demand and serve it (streaming, no cache)"""
        # Validate summary_id format (should be like dou-123456789)
        if not re.match(r'^dou-\d+$', summary_id):
            abort(400, "Invalid summary ID format")
        
        # Load summary to get DOU URL
        summary_path = active_summaries_dir / f"{summary_id}.json"
        if not summary_path.exists():
            app.logger.warning(f"Summary not found for PDF download: {summary_id}")
            abort(404, "Summary not found")
        
        try:
            with summary_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            
            source_meta = data.get("_source", {})
            metadata = data.get("metadata", {}) if isinstance(data.get("metadata"), dict) else {}

            # Use configured DOU URL pattern
            from src.config.dou_urls import get_dou_config
            dou_config = get_dou_config()

            # Candidate titles for legacy/migrated files that may not have _source.url_title.
            url_title = (source_meta.get("url_title") or "").strip()
            
            # Check if url_title is marked as invalid
            if url_title.startswith("__INVALID__"):
                error_msg = source_meta.get("url_title_error", "URL não disponível no DOU")
                app.logger.warning(f"PDF download attempted for invalid URL: {summary_id}")
                abort(404, f"Este documento não está mais disponível no DOU. {error_msg}")
            
            # Validate url_title pattern (should not be just numbers like "2025-687495896")
            if url_title and is_invalid_year_number_slug(url_title):
                app.logger.warning(f"PDF download attempted with invalid url_title pattern: {url_title}")
                abort(404, f"URL inválida detectada. Este documento pode ter sido removido do DOU ou ter metadados incompletos.")
            
            pdf_filename = (source_meta.get("pdf_filename") or "").strip()
            canonical_summary = (source_meta.get("canonical_summary") or "").strip()
            document_id = str(source_meta.get("document_id") or "").strip()
            resolved_title_by_document_id = ""

            candidate_titles = []
            rebuilt_from_legacy = ""
            if url_title:
                rebuilt = rebuild_legacy_slug(url_title, str(metadata.get("edital_numero") or ""))
                if rebuilt:
                    rebuilt_from_legacy = rebuilt
                    candidate_titles.append(rebuilt)
                candidate_titles.append(url_title)
            if pdf_filename:
                # Skip pdf_filename if it matches invalid pattern
                stem = Path(pdf_filename).stem
                if not is_invalid_year_number_slug(stem):
                    rebuilt_stem = rebuild_legacy_slug(stem, str(metadata.get("edital_numero") or ""))
                    if rebuilt_stem:
                        candidate_titles.append(rebuilt_stem)
                    candidate_titles.append(stem)
            if canonical_summary:
                candidate_titles.append(Path(canonical_summary).stem)

            # Extra fallback: resolve url_title from legacy document_id.
            if document_id:
                try:
                    from src.extraction.scraper import resolve_url_title_by_document_id
                    resolved_title = resolve_url_title_by_document_id(document_id)
                    if resolved_title:
                        resolved_title_by_document_id = resolved_title.strip()
                        candidate_titles.append(resolved_title)
                except Exception as resolver_error:
                    app.logger.warning(
                        f"Failed to resolve url_title by document_id={document_id} for {summary_id}: {resolver_error}"
                    )

            # Keep order and remove duplicates/empties.
            normalized_candidates = []
            seen = set()
            for candidate in candidate_titles:
                value = candidate.strip()
                if value and value not in seen:
                    seen.add(value)
                    normalized_candidates.append(value)

            if not normalized_candidates:
                app.logger.warning(f"No URL metadata in summary {summary_id}")
                abort(404, "DOU URL metadata not available for this document")
            
        except HTTPException:
            raise
        except Exception as e:
            app.logger.error(f"Error loading summary {summary_id}: {e}")
            abort(500, "Error loading document metadata")
        
        # Import PDF export here (lazy import to avoid circular deps)
        try:
            from src.export.pdf_export import save_concurso_pdf
            import tempfile
            
            # Download to temporary file (will be cleaned up after serving)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_path = tmp_file.name
            
            app.logger.info(f"Downloading PDF from DOU: {summary_id} user={current_user.id}")

            last_result = ""
            chosen_title = ""
            for candidate_title in normalized_candidates:
                dou_url = dou_config.get_document_url(candidate_title)
                concurso_data = {'url': dou_url, 'url_title': candidate_title}
                last_result = save_concurso_pdf(concurso_data, output_path=tmp_path)
                if isinstance(last_result, str) and last_result.startswith("Content saved"):
                    chosen_title = candidate_title
                    break

            if not (isinstance(last_result, str) and last_result.startswith("Content saved")):
                # Record failure for health monitoring
                alert_needed = dou_config.record_component_failure("pdf_download")
                if alert_needed:
                    flash("⚠️ ALERTA: Múltiplas falhas consecutivas ao baixar PDFs do DOU. A URL pode ter mudado!", "danger")

                app.logger.error(
                    f"PDF download failed for {summary_id}. Candidates tried={normalized_candidates}. Last result={last_result}"
                )
                abort(500, "Failed to download PDF from DOU using available URL metadata")
            
            # Record success
            dou_config.record_component_success("pdf_download")

            # Persist resolved url_title when legacy document_id fallback was used successfully.
            if (
                not url_title
                and resolved_title_by_document_id
                and chosen_title == resolved_title_by_document_id
            ):
                try:
                    source_meta["url_title"] = resolved_title_by_document_id
                    source_meta["url_title_resolved_at"] = datetime.now().isoformat()
                    source_meta["url_title_resolved_by"] = "document_id_fallback"
                    with summary_path.open("w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    app.logger.info(
                        f"Persisted url_title for {summary_id}: {resolved_title_by_document_id}"
                    )
                except Exception as persist_error:
                    app.logger.warning(
                        f"Could not persist resolved url_title for {summary_id}: {persist_error}"
                    )

            # Persist reconstructed legacy url_title when it works.
            if (
                url_title
                and rebuilt_from_legacy
                and chosen_title == rebuilt_from_legacy
                and chosen_title != url_title
            ):
                try:
                    source_meta["url_title"] = chosen_title
                    source_meta["url_title_resolved_at"] = datetime.now().isoformat()
                    source_meta["url_title_resolved_by"] = "legacy_prefix_reconstruction"
                    with summary_path.open("w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    app.logger.info(
                        f"Persisted reconstructed url_title for {summary_id}: {chosen_title}"
                    )
                except Exception as persist_error:
                    app.logger.warning(
                        f"Could not persist reconstructed url_title for {summary_id}: {persist_error}"
                    )
            
            # Serve the temporary file
            app.logger.info(
                f"PDF served: {summary_id} user={current_user.id} title_source={chosen_title or normalized_candidates[0]}"
            )
            
            @after_this_request
            def cleanup(response):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                return response
            
            return send_file(
                tmp_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"{summary_id}.pdf"
            )
            
        except Exception as e:
            app.logger.error(f"Error downloading PDF from DOU: {e}")
            abort(500, f"Error downloading PDF: {str(e)}")

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors with user-friendly message"""
        if request.path.startswith('/editais/'):
            message = "PDF não encontrado. Este arquivo pode ter sido extraído temporariamente sem persistência."
        else:
            message = str(error.description) if hasattr(error, 'description') else "Página não encontrada"
        
        return render_template(
            "error.html",
            error_code=404,
            error_title="Não Encontrado",
            error_message=message
        ), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        app.logger.error(f"Internal server error: {error}")
        return render_template(
            "error.html",
            error_code=500,
            error_title="Erro Interno do Servidor",
            error_message="Ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
        ), 500

    return app


if __name__ == "__main__":
    app = create_app()
    
    # Development mode only - Production should use Gunicorn/WSGI
    debug_mode = os.environ.get("DEBUG", "True").lower() == "true"
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    
    if debug_mode:
        app.logger.warning("[WARNING] Running in DEBUG mode - DO NOT use in production!")
    
    app.run(host=host, port=port, debug=debug_mode)
