import unittest
import tempfile
from pathlib import Path
from featuregraph.core.parser_generic import GenericFeatureParser
from featuregraph.core.scanner import WorkspaceScanner
from featuregraph.core.annotator import collect_suggestions, apply_suggestions

class TestGenericFeatureParser(unittest.TestCase):
    def test_parse_go_and_rust(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            go_file = tmp_path / "server.go"
            go_file.write_text("""package main

// @feature [GO-AUTH-01] JWT Auth Middleware
// @depends [GO-CONFIG-01]
func AuthMiddleware(token string) bool {
    if len(token) > 0 {
        return true
    }
    return false
}
""")
            rust_file = tmp_path / "engine.rs"
            rust_file.write_text("""// @feature [RUST-CORE-01] Matrix Solver Engine
pub fn solve_matrix(data: &[f64]) -> Vec<f64> {
    data.to_vec()
}
""")
            scanner = WorkspaceScanner(tmp_path)
            graph = scanner.scan()
            data = graph.to_dict()

            self.assertIn("GO-AUTH-01", data)
            self.assertEqual(data["GO-AUTH-01"]["name"], "JWT Auth Middleware")
            self.assertIn("GO-CONFIG-01", data["GO-AUTH-01"]["depends_on"])
            self.assertEqual(data["GO-AUTH-01"]["locations"][0]["symbol"], "AuthMiddleware")
            self.assertEqual(data["GO-AUTH-01"]["locations"][0]["lines"], [5, 10])

            self.assertIn("RUST-CORE-01", data)
            self.assertEqual(data["RUST-CORE-01"]["name"], "Matrix Solver Engine")

    def test_annotate_java_and_csharp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            java_file = tmp_path / "PaymentService.java"
            java_file.write_text("""public class PaymentService {
    public void processPayment(double amount) {
        System.out.println("Processing");
    }
}
""")
            cs_file = tmp_path / "OrderController.cs"
            cs_file.write_text("""public class OrderController {
    public void PlaceOrder() {
    }
}
""")
            suggestions = collect_suggestions(tmp_path)
            self.assertTrue(len(suggestions) >= 2)
            apply_suggestions(suggestions)

            content_java = java_file.read_text()
            self.assertIn("// @feature [", content_java)

            content_cs = cs_file.read_text()
            self.assertIn("// @feature [", content_cs)

if __name__ == "__main__":
    unittest.main()
