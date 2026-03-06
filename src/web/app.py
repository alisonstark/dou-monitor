from pathlib import Path
import os
import secrets
import logging
import random
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask_wtf.csrf import CSRFProtect
from flask_login import login_user, logout_user, login_required, current_user

from .auth import login_manager, verify_credentials, User
from .security import validate_filename, validate_email, is_safe_url
from .dashboard_service import (
    apply_manual_review,
    categorize_concursos,
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
        categorized = categorize_concursos(filtered)
        abertura_records = categorized["abertura"]
        outros_records = categorized["outros"]
        outros_window_days = config.get("filters", {}).get("default_days", 7)
        outros_filtered = filter_records_by_cache_window(outros_records, outros_window_days)
        outros_window_info = get_cache_coverage_info(records, outros_window_days)

        edit_file = request.args.get("edit", "")
        edit_record = get_record_by_file_name(abertura_records, edit_file)

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
        
        api_url = url_for("concursos_api", **request.args.to_dict(flat=True))

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
        )

    @app.get("/api/concursos")
    @login_required
    def concursos_api():
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
        flash("Configuracoes de filtros salvas.", "success")
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
        flash("Configuracoes de notificacao salvas.", "success")
        return redirect(url_for("index"))

    @app.post("/run/manual")
    @login_required
    def run_manual():
        days_raw = request.form.get("days", "7")
        export_pdf = request.form.get("export_pdf") == "on"
        days = _parse_positive_int(days_raw, 7)
        
        # 🔒 SECURITY: Log manual execution
        app.logger.info(f"Manual execution: user={current_user.id} days={days} export_pdf={export_pdf} ip={request.remote_addr}")
        
        result = run_manual_monitoring(BASE_DIR, days, export_pdf)
        
        if result["success"]:
            if export_pdf:
                msg = f"✅ Processamento concluído! {result['processed']} summaries atualizados em data/summaries/. "
                msg += f"PDFs salvos em editais/: {result.get('saved_pdfs', 0)}. "
                msg += f"Total encontrado: {result['total_concursos']} ({result['abertura_concursos']} aberturas, {result['outros_concursos']} outros). "
                if result['errors'] > 0:
                    msg += f"⚠️ {result['errors']} erro(s). "
                msg += "Atualize a página para visualizar."
                flash(msg, "success")
            else:
                msg = f"🔍 Busca concluída: {result['total_concursos']} concursos encontrados "
                msg += f"({result['abertura_concursos']} aberturas, {result['outros_concursos']} outros). "
                msg += f"Summaries extraídos/atualizados: {result['processed']}. "
                msg += "PDFs não foram persistidos em disco (modo temporário)."
                flash(msg, "warning")
        else:
            flash(f"Erro: {result['error_message']}", "error")
        
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
                fields_str = ", ".join([f.split(".")[-1] for f in changed])
                flash(f"✅ MIT aplicado: {review_result['message']} Campos alterados: {fields_str}", "success")
            else:
                flash(f"ℹ️ {review_result['message']}", "success")
        else:
            flash(f"❌ Erro ao aplicar MIT: {review_result['message']}", "error")

        if next_query:
            safe_query = next_query.lstrip("?")
            return redirect(url_for("index") + f"?{safe_query}")
        return redirect(url_for("index"))

    @app.get("/editais/<filename>")
    @login_required
    def serve_edital(filename):
        """Serve PDF files from the editais/ directory with path traversal protection"""
        # 🔒 SECURITY: Validate filename to prevent path traversal
        is_valid, error_msg = validate_filename(filename)
        if not is_valid:
            app.logger.warning(f"Path traversal attempt: file={filename} user={current_user.id} ip={request.remote_addr}")
            abort(400, f"Invalid filename: {error_msg}")
        
        # Validate extension
        if not filename.lower().endswith('.pdf'):
            abort(400, "Only PDF files allowed")
        
        editais_dir = BASE_DIR / "editais"
        full_path = editais_dir / filename
        
        # Ensure resolved path is within editais_dir
        try:
            editais_dir_resolved = editais_dir.resolve()
            full_path_resolved = full_path.resolve()
            
            if not str(full_path_resolved).startswith(str(editais_dir_resolved)):
                app.logger.warning(f"Path traversal blocked: {filename} user={current_user.id}")
                abort(403, "Access denied")
            
            if not full_path_resolved.exists():
                abort(404, "File not found")
        
        except Exception as e:
            app.logger.error(f"Error serving file {filename}: {e}")
            abort(500, "Internal server error")
        
        app.logger.info(f"PDF download: file={filename} user={current_user.id} ip={request.remote_addr}")
        return send_from_directory(editais_dir, filename)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
