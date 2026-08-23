import unittest
import tempfile
from pathlib import Path
from featuregraph.core.scanner import WorkspaceScanner

class TestDependencyResolver(unittest.TestCase):
    def test_python_automated_call_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # File 1: Auth service
            (tmp_path / "auth.py").write_text("""# @feature [AUTH-01] Token Validator
def validate_token(token: str) -> bool:
    return len(token) > 5

# @feature [AUTH-02] Session Manager
class SessionManager:
    def create_session(self, user_id: str):
        pass
""")

            # File 2: Order service calling Auth
            (tmp_path / "orders.py").write_text("""# @feature [ORDER-01] Place Order Endpoint
def place_order(token: str, item_id: str):
    is_valid = validate_token(token)
    session = SessionManager()
    return {"status": "ok"}
""")

            scanner = WorkspaceScanner(tmp_path)
            graph = scanner.scan()
            data = graph.to_dict()

            self.assertIn("ORDER-01", data)
            self.assertIn("AUTH-01", data)
            self.assertIn("AUTH-02", data)

            # Automated dependency resolution verification:
            order_deps = data["ORDER-01"].get("depends_on", [])
            self.assertIn("AUTH-01", order_deps)
            self.assertIn("AUTH-02", order_deps)

            # Reverse callers verification:
            auth1_callers = data["AUTH-01"].get("called_by", [])
            self.assertIn("ORDER-01", auth1_callers)

            auth2_callers = data["AUTH-02"].get("called_by", [])
            self.assertIn("ORDER-01", auth2_callers)

    def test_typescript_automated_component_usage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            (tmp_path / "Avatar.tsx").write_text("""// @feature [UI-AVATAR] Avatar Component
export const Avatar = () => <div>Avatar</div>;
""")

            (tmp_path / "Profile.tsx").write_text("""// @feature [PAGE-PROFILE] Profile Page
export const ProfilePage = () => {
    return (
        <div>
            <Avatar />
        </div>
    );
};
""")

            scanner = WorkspaceScanner(tmp_path)
            graph = scanner.scan()
            data = graph.to_dict()

            self.assertIn("PAGE-PROFILE", data)
            self.assertIn("UI-AVATAR", data)

            profile_deps = data["PAGE-PROFILE"].get("depends_on", [])
            self.assertIn("UI-AVATAR", profile_deps)

            avatar_callers = data["UI-AVATAR"].get("called_by", [])
            self.assertIn("PAGE-PROFILE", avatar_callers)

if __name__ == "__main__":
    unittest.main()
