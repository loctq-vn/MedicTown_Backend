from app.main import app


def test_chat_routes_are_registered():
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set()) or set()
    }

    assert ("/api/chat/conversation", "POST") in routes
    assert ("/api/chat/messages", "GET") in routes
    assert ("/api/chat/messages", "POST") in routes
    assert ("/api/chat/read", "PATCH") in routes
    assert ("/api/chat/seller/conversations", "GET") in routes
    assert any(route.path == "/api/chat/ws" for route in app.routes)
