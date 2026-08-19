"""Serve Claude conversation search results over HTTP."""

import argparse

from flask import Flask, jsonify, render_template, request

from claude_search import InvalidSearchTerm, ProjectsDirectoryNotFound, search


def is_enabled(value):
    """Return whether a query-string flag reads as switched on."""
    return value.lower() in {"true", "1", "on"}


def serialize_result(result):
    """Convert a search result into the public JSON response shape."""
    return {
        "mtime": result.mtime,
        "cwd": result.cwd,
        "conv_id": result.conv_id,
        "title": result.title,
        "match": result.match,
        "relative_date": result.relative_date,
        "title_date": result.title_date,
        "match_date": result.match_date,
        "resume_command": result.resume_command,
        "title_segments": [
            {"text": segment.text, "highlighted": segment.highlighted}
            for segment in result.title_segments
        ],
        "match_segments": [
            {"text": segment.text, "highlighted": segment.highlighted}
            for segment in result.match_segments
        ],
    }


def create_app(projects_dir=None):
    """Create the Flask application for Claude conversation search."""
    app = Flask(__name__)
    app.config["PROJECTS_DIR"] = projects_dir

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/search")
    def api_search():
        term = request.args.get("term", "")
        path = request.args.get("path", "")
        case_sensitive = is_enabled(request.args.get("case_sensitive", "false"))
        include_assistant = is_enabled(request.args.get("include_assistant", "false"))
        try:
            results = search(
                term,
                case_sensitive=case_sensitive,
                projects_dir=app.config["PROJECTS_DIR"],
                path_prefix=path,
                include_assistant=include_assistant,
            )
        except InvalidSearchTerm as error:
            return jsonify({
                "error": {"code": "invalid_search", "message": str(error)}
            }), 400
        except ProjectsDirectoryNotFound:
            return jsonify({
                "error": {
                    "code": "history_unavailable",
                    "message": "No Claude history found.",
                }
            }), 503
        except Exception:
            return jsonify({
                "error": {
                    "code": "server_error",
                    "message": "Search failed unexpectedly.",
                }
            }), 500

        return jsonify({
            "term": term,
            "path": path,
            "case_sensitive": case_sensitive,
            "include_assistant": include_assistant,
            "results": [serialize_result(result) for result in results],
        })

    return app


def parse_args(argv=None):
    """Parse the server bind address and port."""
    parser = argparse.ArgumentParser(description="Serve Claude search results")
    parser.add_argument("-b", "--bind", default="127.0.0.1")
    parser.add_argument("-p", "--port", type=int, default=5000)
    return parser.parse_args(argv)


def main(argv=None):
    """Run the Flask development server."""
    args = parse_args(argv)
    app.run(host=args.bind, port=args.port)


app = create_app()


if __name__ == "__main__":
    main()
