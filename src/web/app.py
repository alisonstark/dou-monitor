from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from .dashboard_service import (
    filter_summaries,
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
    app.config["SECRET_KEY"] = "doumon-dashboard-dev"

    active_summaries_dir = summaries_dir or DEFAULT_SUMMARIES_DIR
    active_config_path = config_path or DEFAULT_CONFIG_PATH

    @app.context_processor
    def utility_processor():
        def url_with_updates(**updates):
            current = request.args.to_dict(flat=True)
            for key, value in updates.items():
                current[key] = str(value)
            return url_for("index", **current)

        return {"url_with_updates": url_with_updates}

    @app.get("/")
    def index():
        records = load_summaries(active_summaries_dir)
        filters = {
            "q": request.args.get("q", ""),
            "orgao": request.args.get("orgao", ""),
            "cargo": request.args.get("cargo", ""),
            "banca": request.args.get("banca", ""),
            "date_from": request.args.get("date_from", ""),
            "date_to": request.args.get("date_to", ""),
        }
        sort_by = request.args.get("sort_by", "data_prova")
        sort_dir = request.args.get("sort_dir", "desc")
        page = _parse_positive_int(request.args.get("page", "1"), 1)
        page_size = _parse_positive_int(request.args.get("page_size", "10"), 10)

        filtered = filter_summaries(records, filters)
        sorted_records = sort_summaries(filtered, sort_by, sort_dir)
        page_items, page_meta = paginate_summaries(sorted_records, page, page_size)
        metrics = summarize_metrics(filtered)
        config = load_dashboard_config(active_config_path)

        api_url = url_for("concursos_api", **request.args.to_dict(flat=True))

        return render_template(
            "dashboard.html",
            records=page_items,
            metrics=metrics,
            filters=filters,
            config=config,
            sort_by=sort_by,
            sort_dir=sort_dir,
            page_meta=page_meta,
            api_url=api_url,
        )

    @app.get("/api/concursos")
    def concursos_api():
        records = load_summaries(active_summaries_dir)
        filters = {
            "q": request.args.get("q", ""),
            "orgao": request.args.get("orgao", ""),
            "cargo": request.args.get("cargo", ""),
            "banca": request.args.get("banca", ""),
            "date_from": request.args.get("date_from", ""),
            "date_to": request.args.get("date_to", ""),
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
    def save_notifications():
        config = load_dashboard_config(active_config_path)

        threshold_raw = request.form.get("threshold", "1")
        email_to = request.form.get("email_to", "").strip()
        webhook_url = request.form.get("webhook_url", "").strip()
        desktop_enabled = request.form.get("desktop_enabled") == "on"

        threshold = _parse_positive_int(threshold_raw, 1)

        config["notifications"]["threshold"] = threshold
        config["notifications"]["email_to"] = email_to
        config["notifications"]["webhook_url"] = webhook_url
        config["notifications"]["desktop_enabled"] = desktop_enabled

        save_dashboard_config(active_config_path, config)
        flash("Configuracoes de notificacao salvas.", "success")
        return redirect(url_for("index"))

    @app.post("/run/manual")
    def run_manual():
        days_raw = request.form.get("days", "7")
        export_pdf = request.form.get("export_pdf") == "on"
        days = _parse_positive_int(days_raw, 7)
        
        result = run_manual_monitoring(BASE_DIR, days, export_pdf)
        
        if result["success"]:
            msg = f"Monitoramento concluido: {result['abertura_concursos']} abertura(s) de {result['total_concursos']} total."
            if export_pdf:
                msg += f" Processados: {result['processed']}, Erros: {result['errors']}."
            flash(msg, "success")
        else:
            flash(f"Erro: {result['error_message']}", "error")
        
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
