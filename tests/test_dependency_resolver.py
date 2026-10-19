import json
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

    def test_same_named_methods_resolved_by_qualname(self):
        """Two features sharing a method name: only the qualified match gets the edge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "a.py").write_text("""# @feature [A-CLASS] Alpha Service
class Alpha:
    # @feature [A-METHOD] Alpha parse
    def parse_file(self, x):
        return x
""")
            (tmp_path / "b.py").write_text("""# @feature [B-CLASS] Beta Service
class Beta:
    # @feature [B-METHOD] Beta parse
    def parse_file(self, x):
        return x
""")
            (tmp_path / "user.py").write_text("""# @feature [USER-01] User flow
def run(alpha):
    return Alpha.parse_file(alpha, 1)
""")

            data = WorkspaceScanner(tmp_path).scan().to_dict()
            user_deps = data["USER-01"].get("depends_on", [])
            self.assertIn("A-METHOD", user_deps)
            self.assertIn("A-CLASS", user_deps)
            self.assertNotIn("B-METHOD", user_deps)

    def test_bare_ambiguous_name_skipped(self):
        """A bare call to a name defined by multiple features produces no guessed edge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "a.py").write_text("""# @feature [A-METHOD] Alpha parse
def parse_file(x):
    return x
""")
            (tmp_path / "b.py").write_text("""# @feature [B-METHOD] Beta parse
def parse_file(x):
    return x
""")
            (tmp_path / "caller.py").write_text("""# @feature [CALLER-01] Caller
def invoke(x):
    return parse_file(x)
""")

            data = WorkspaceScanner(tmp_path).scan().to_dict()
            self.assertEqual(data["CALLER-01"].get("depends_on", []), [])

    def test_python_local_assignment_is_not_a_dependency(self):
        """A local variable that shadows a feature name is not a dependency."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "helper.py").write_text(
                "# @feature [B-01] Helper\ndef helper():\n    return 1\n"
            )
            (tmp_path / "caller.py").write_text(
                "# @feature [A-01] Caller\ndef caller():\n    helper = 2\n    return helper\n"
            )

            data = WorkspaceScanner(tmp_path).scan().to_dict()
            self.assertEqual(data["A-01"].get("depends_on", []), [])

    def test_scan_is_deterministic(self):
        """Two scans of the same tree produce byte-identical graph data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "z.py").write_text("# @feature [Z-01] Z\ndef z(): pass\n")
            (tmp_path / "a.py").write_text("""# @feature [A-01] A
def a():
    return z()
""")
            (tmp_path / "m.py").write_text("""# @feature [M-01] M
class M:
    # @feature [M-02] M call
    def go(self):
        return a()
""")

            first = json.dumps(WorkspaceScanner(tmp_path).scan().to_dict(), sort_keys=True)
            second = json.dumps(WorkspaceScanner(tmp_path).scan().to_dict(), sort_keys=True)
            self.assertEqual(first, second)

if __name__ == "__main__":
    unittest.main()
