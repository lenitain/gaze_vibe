"""GazeVibe 后端统一错误处理"""

from flask import jsonify


class APIError(Exception):
    """API 异常，携带状态码和错误信息"""

    def __init__(self, message, status_code=400, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def to_response(self):
        body = {"success": False, "error": self.message}
        if self.details:
            body["details"] = self.details
        return jsonify(body), self.status_code


def register_error_handlers(app):
    """在 Flask app 上注册统一错误处理器"""

    @app.errorhandler(APIError)
    def handle_api_error(error):
        return error.to_response()

    @app.errorhandler(400)
    def handle_bad_request(error):
        return jsonify({"success": False, "error": "请求参数错误"}), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        return jsonify({"success": False, "error": "接口不存在"}), 404

    @app.errorhandler(500)
    def handle_internal_error(error):
        return jsonify({"success": False, "error": "服务器内部错误"}), 500
