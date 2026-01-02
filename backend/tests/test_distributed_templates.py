"""
Tests for distributed problem templates.

This module tests:
1. Template loading for all 16 problems across all 5 languages (Python, Go, Java, C++, Rust)
2. Proto file loading for all 16 problems
3. Template validation - ensuring TODOs are stubs, not implementations
4. Template structure validation
"""

import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.api.distributed import (
    get_template_from_filesystem,
    get_proto_from_filesystem,
    PROBLEM_TYPE_CONFIG,
    DEFAULT_PROBLEM_IDS,
)


# ============================================================================
# Test Constants
# ============================================================================

ALL_PROBLEM_TYPES = list(PROBLEM_TYPE_CONFIG.keys())
ALL_LANGUAGES = ["python", "go", "java", "cpp", "rust"]

# Expected minimum line counts for templates (to ensure they're not empty)
MIN_TEMPLATE_LINES = 50


# ============================================================================
# Template Loading Tests
# ============================================================================

class TestTemplateLoading:
    """Tests for template file loading."""

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    @pytest.mark.parametrize("language", ALL_LANGUAGES)
    def test_template_loads_successfully(self, problem_type, language):
        """Test that templates load for all problem/language combinations."""
        template = get_template_from_filesystem(language, problem_type)

        # Should not be empty or error message
        assert template is not None
        assert len(template) > 0
        assert "Template file not found" not in template, \
            f"Template not found for {problem_type}/{language}"
        assert "Template not available" not in template, \
            f"Template not available for {problem_type}/{language}"
        assert "permission denied" not in template.lower(), \
            f"Permission denied for {problem_type}/{language}"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    @pytest.mark.parametrize("language", ALL_LANGUAGES)
    def test_template_has_minimum_content(self, problem_type, language):
        """Test that templates have substantial content."""
        template = get_template_from_filesystem(language, problem_type)
        lines = template.strip().split('\n')

        assert len(lines) >= MIN_TEMPLATE_LINES, \
            f"Template for {problem_type}/{language} has only {len(lines)} lines, expected >= {MIN_TEMPLATE_LINES}"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_proto_loads_successfully(self, problem_type):
        """Test that proto files load for all problems."""
        proto = get_proto_from_filesystem(problem_type)

        assert proto is not None
        assert len(proto) > 0
        assert "Proto file not found" not in proto, \
            f"Proto not found for {problem_type}"
        assert "permission denied" not in proto.lower(), \
            f"Permission denied for {problem_type}"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_proto_has_service_definition(self, problem_type):
        """Test that proto files contain service definitions."""
        proto = get_proto_from_filesystem(problem_type)

        assert "service " in proto, \
            f"Proto for {problem_type} should contain service definitions"
        assert "syntax = \"proto3\"" in proto, \
            f"Proto for {problem_type} should use proto3 syntax"


# ============================================================================
# Template Stub Validation Tests
# ============================================================================

class TestTemplateStubs:
    """Tests to ensure templates are stubs, not implementations."""

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_python_templates_are_stubs(self, problem_type):
        """Test that Python templates have stub implementations."""
        template = get_template_from_filesystem("python", problem_type)

        # Check for TODO markers
        assert "TODO" in template, \
            f"Python template for {problem_type} should contain TODO comments"

        # Check for common stub patterns
        stub_patterns = [
            "pass",  # Empty method body
            "return False",  # Stub return
            "return None",  # Stub return
            "return 0",  # Stub return for numbers
            "raise",  # Can raise NotImplementedError
            "Not implemented",  # Error message stub
            "success = False",  # Response stub pattern
            "return (False",  # Tuple stub return
        ]
        has_stub_pattern = any(pattern in template for pattern in stub_patterns)
        assert has_stub_pattern, \
            f"Python template for {problem_type} should contain stub patterns (pass, return False, etc.)"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_go_templates_are_stubs(self, problem_type):
        """Test that Go templates have stub implementations."""
        template = get_template_from_filesystem("go", problem_type)

        # Check for TODO markers
        assert "TODO" in template, \
            f"Go template for {problem_type} should contain TODO comments"

        # Check for common stub patterns in Go
        stub_patterns = [
            "return false",
            "return nil",
            "return 0",
            'return ""',
            "// TODO: Implement",
        ]
        has_stub_pattern = any(pattern in template for pattern in stub_patterns)
        assert has_stub_pattern, \
            f"Go template for {problem_type} should contain stub patterns"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_java_templates_are_stubs(self, problem_type):
        """Test that Java templates have stub implementations."""
        template = get_template_from_filesystem("java", problem_type)

        # Check for TODO markers
        assert "TODO" in template, \
            f"Java template for {problem_type} should contain TODO comments"

        # Check for common stub patterns in Java
        stub_patterns = [
            "throw new UnsupportedOperationException",
            "return false",
            "return null",
            "return 0",
            "// TODO: Implement",
        ]
        has_stub_pattern = any(pattern in template for pattern in stub_patterns)
        assert has_stub_pattern, \
            f"Java template for {problem_type} should contain stub patterns"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_cpp_templates_are_stubs(self, problem_type):
        """Test that C++ templates have stub implementations."""
        template = get_template_from_filesystem("cpp", problem_type)

        # Check for TODO markers
        assert "TODO" in template, \
            f"C++ template for {problem_type} should contain TODO comments"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_rust_templates_are_stubs(self, problem_type):
        """Test that Rust templates have stub implementations."""
        template = get_template_from_filesystem("rust", problem_type)

        # Check for TODO markers
        assert "TODO" in template or "todo!" in template, \
            f"Rust template for {problem_type} should contain TODO comments or todo! macro"


# ============================================================================
# Template Structure Tests
# ============================================================================

class TestTemplateStructure:
    """Tests for template code structure and quality."""

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_python_template_has_imports(self, problem_type):
        """Test that Python templates have necessary imports."""
        template = get_template_from_filesystem("python", problem_type)

        # Should have standard imports
        assert "import " in template or "from " in template, \
            f"Python template for {problem_type} should have import statements"

        # Should have gRPC imports for distributed systems
        assert "grpc" in template.lower(), \
            f"Python template for {problem_type} should import grpc"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_python_template_has_main(self, problem_type):
        """Test that Python templates have a main entry point."""
        template = get_template_from_filesystem("python", problem_type)

        assert 'if __name__ == "__main__"' in template or "def main()" in template, \
            f"Python template for {problem_type} should have main entry point"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_go_template_has_package(self, problem_type):
        """Test that Go templates have package declaration."""
        template = get_template_from_filesystem("go", problem_type)

        assert "package main" in template, \
            f"Go template for {problem_type} should have package main declaration"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_go_template_has_main(self, problem_type):
        """Test that Go templates have main function."""
        template = get_template_from_filesystem("go", problem_type)

        assert "func main()" in template, \
            f"Go template for {problem_type} should have main function"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_java_template_has_class(self, problem_type):
        """Test that Java templates have a class declaration."""
        template = get_template_from_filesystem("java", problem_type)

        assert "public class" in template or "class " in template, \
            f"Java template for {problem_type} should have class declaration"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_java_template_has_main(self, problem_type):
        """Test that Java templates have main method."""
        template = get_template_from_filesystem("java", problem_type)

        assert "public static void main" in template, \
            f"Java template for {problem_type} should have main method"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_cpp_template_has_includes(self, problem_type):
        """Test that C++ templates have include statements."""
        template = get_template_from_filesystem("cpp", problem_type)

        assert "#include" in template, \
            f"C++ template for {problem_type} should have #include statements"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_cpp_template_has_main(self, problem_type):
        """Test that C++ templates have main function."""
        template = get_template_from_filesystem("cpp", problem_type)

        assert "int main(" in template, \
            f"C++ template for {problem_type} should have main function"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_rust_template_has_main(self, problem_type):
        """Test that Rust templates have main function."""
        template = get_template_from_filesystem("rust", problem_type)

        assert "fn main()" in template, \
            f"Rust template for {problem_type} should have main function"


# ============================================================================
# Problem Configuration Tests
# ============================================================================

class TestProblemConfiguration:
    """Tests for problem type configuration."""

    def test_all_19_problems_configured(self):
        """Test that all 19 problems are configured."""
        assert len(PROBLEM_TYPE_CONFIG) == 19, \
            f"Expected 19 problem types, got {len(PROBLEM_TYPE_CONFIG)}"

    def test_problem_ids_match_config(self):
        """Test that DEFAULT_PROBLEM_IDS match PROBLEM_TYPE_CONFIG."""
        for problem_id, problem_type in DEFAULT_PROBLEM_IDS.items():
            assert problem_type in PROBLEM_TYPE_CONFIG, \
                f"Problem type {problem_type} (ID {problem_id}) not in PROBLEM_TYPE_CONFIG"

    def test_all_problem_types_have_required_fields(self):
        """Test that all problem configs have required fields."""
        required_fields = ["directory", "proto_file", "java_class", "test_runner"]

        for problem_type, config in PROBLEM_TYPE_CONFIG.items():
            for field in required_fields:
                assert field in config, \
                    f"Problem type {problem_type} missing required field: {field}"

    def test_problem_directories_exist(self):
        """Test that all problem directories exist."""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        for problem_type, config in PROBLEM_TYPE_CONFIG.items():
            problem_dir = os.path.join(base_path, "distributed_problems", config["directory"])
            assert os.path.isdir(problem_dir), \
                f"Directory not found for {problem_type}: {problem_dir}"

    def test_proto_files_exist(self):
        """Test that all proto files exist."""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        for problem_type, config in PROBLEM_TYPE_CONFIG.items():
            proto_path = os.path.join(
                base_path, "distributed_problems",
                config["directory"], "proto", config["proto_file"]
            )
            assert os.path.isfile(proto_path), \
                f"Proto file not found for {problem_type}: {proto_path}"


# ============================================================================
# Template Content Validation Tests
# ============================================================================

class TestTemplateContentValidation:
    """Tests for validating template content doesn't have implementations."""

    # Patterns that indicate full implementations (should NOT be in stubs)
    # Note: These are very specific patterns to detect actual algorithm implementations
    IMPLEMENTATION_PATTERNS = {
        "python": [
            # Token bucket specific - actual refill calculation
            ("refill_tokens", r"bucket\.tokens\s*=\s*min\(bucket\.tokens\s*\+"),
            # Try consume - actual token checking and consuming
            ("try_consume", r"bucket\.tokens\s*-=\s*tokens"),
            # CRDT increment - actual counter increment implementation
            ("increment_counter", r"self\.state\[.*\]\[\"counter\"\]\s*\+="),
        ],
        "go": [
            # Token bucket specific
            ("RefillTokens", r"bucket\.Tokens\s*=\s*min\("),
            ("TryConsume", r"if bucket\.Tokens\s*>=\s*tokens"),
        ],
        "java": [
            # Token bucket specific
            ("refillTokens", r"bucket\.tokens\s*=\s*Math\.min\("),
            ("tryConsume", r"if\s*\(bucket\.tokens\s*>=\s*tokens\)"),
        ],
    }

    @pytest.mark.parametrize("problem_type", ["token_bucket", "leaky_bucket", "consistent_hashing", "crdt"])
    def test_python_no_full_implementations(self, problem_type):
        """Test that Python templates don't have full implementations for key methods."""
        import re
        template = get_template_from_filesystem("python", problem_type)

        for pattern_name, pattern in self.IMPLEMENTATION_PATTERNS.get("python", []):
            match = re.search(pattern, template)
            assert match is None, \
                f"Python template for {problem_type} appears to have implementation for {pattern_name}"

    @pytest.mark.parametrize("problem_type", ["token_bucket", "leaky_bucket"])
    def test_go_no_full_implementations(self, problem_type):
        """Test that Go templates don't have full implementations for key methods."""
        import re
        template = get_template_from_filesystem("go", problem_type)

        for pattern_name, pattern in self.IMPLEMENTATION_PATTERNS.get("go", []):
            match = re.search(pattern, template)
            assert match is None, \
                f"Go template for {problem_type} appears to have implementation for {pattern_name}"

    @pytest.mark.parametrize("problem_type", ["token_bucket", "leaky_bucket"])
    def test_java_no_full_implementations(self, problem_type):
        """Test that Java templates don't have full implementations for key methods."""
        import re
        template = get_template_from_filesystem("java", problem_type)

        for pattern_name, pattern in self.IMPLEMENTATION_PATTERNS.get("java", []):
            match = re.search(pattern, template)
            assert match is None, \
                f"Java template for {problem_type} appears to have implementation for {pattern_name}"


# ============================================================================
# Template Files Physical Check
# ============================================================================

class TestTemplateFilesExist:
    """Test that all template files physically exist on disk."""

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    @pytest.mark.parametrize("language,file_pattern", [
        ("python", "python/server.py"),
        ("go", "go/server.go"),
        ("cpp", "cpp/server.cpp"),
        ("rust", "rust/src/main.rs"),
    ])
    def test_template_file_exists(self, problem_type, language, file_pattern):
        """Test that template files exist on disk."""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config = PROBLEM_TYPE_CONFIG[problem_type]

        template_path = os.path.join(
            base_path, "distributed_problems",
            config["directory"], "templates", file_pattern
        )

        assert os.path.isfile(template_path), \
            f"Template file not found: {template_path}"

    @pytest.mark.parametrize("problem_type", ALL_PROBLEM_TYPES)
    def test_java_template_file_exists(self, problem_type):
        """Test that Java template files exist with correct class names."""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config = PROBLEM_TYPE_CONFIG[problem_type]
        java_class = config["java_class"]

        template_path = os.path.join(
            base_path, "distributed_problems",
            config["directory"], "templates", "java", f"{java_class}.java"
        )

        assert os.path.isfile(template_path), \
            f"Java template file not found: {template_path}"
