"""
Unit tests for JavaScript/TypeScript AST parser.
Validates:
- Distinction between MethodDefinition and CallExpression
- Calls like super(), authenticate(), and json() are not treated as methods
- Arrow function properties on classes
- Comment and string brace robustness
"""
import tempfile
from pathlib import Path
from backend.parsers.javascript_parser import JavaScriptParser, TypeScriptParser


def test_js_parser_distinguishes_methods_from_calls():
    """Verify super(), authenticate(), and json() calls are not parsed as methods."""
    code = """
    class AuthenticationController extends BaseController {
        constructor(service) {
            super(service);
            this.service = service;
        }

        async login(req, res) {
            super();
            this.authenticate();
            authenticate();
            return res.json({ success: true });
        }

        logout(req, res) {
            req.session.destroy();
            json();
        }

        handleToken = async (token) => {
            console.log("Token received", token);
        };
    }
    """

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(code)
        fname = f.name

    parser = JavaScriptParser(fname, "auth.js")
    result = parser.parse()

    assert result["success"] is True
    assert len(result["classes"]) == 1

    cls = result["classes"][0]
    assert cls["name"] == "AuthenticationController"
    assert cls["extends"] == "BaseController"

    method_names = [m["name"] for m in cls["methods"]]

    # Valid methods
    assert "constructor" in method_names
    assert "login" in method_names
    assert "logout" in method_names
    assert "handleToken" in method_names

    # Ensure calls are NOT mistakenly treated as methods
    assert "super" not in method_names
    assert "authenticate" not in method_names
    assert "json" not in method_names


def test_js_parser_handles_braces_in_strings_and_comments():
    """Verify braces inside strings or comments do not corrupt depth tracking."""
    code = """
    class SafeClass {
        // Line comment with { braces }
        /* Block comment with {
           more braces
        } */
        methodOne() {
            const str1 = "}";
            const str2 = '{';
            const template = `} ${1+1} {`;
            return str1;
        }

        methodTwo() {
            return true;
        }
    }
    """

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(code)
        fname = f.name

    parser = JavaScriptParser(fname, "safe.js")
    result = parser.parse()

    cls = result["classes"][0]
    method_names = [m["name"] for m in cls["methods"]]

    assert method_names == ["methodOne", "methodTwo"]


def test_ts_parser_interface_and_types():
    """Verify TypeScript parser extracts interfaces and typed classes."""
    code = """
    interface UserDTO {
        id: string;
        username: string;
    }

    class UserService {
        async getUser(id: string): Promise<UserDTO> {
            return { id, username: "alice" };
        }
    }
    """

    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as f:
        f.write(code)
        fname = f.name

    parser = TypeScriptParser(fname, "user.ts")
    result = parser.parse()

    assert len(result["interfaces"]) == 1
    assert result["interfaces"][0]["name"] == "UserDTO"
    assert len(result["classes"]) == 1
    assert result["classes"][0]["methods"][0]["name"] == "getUser"
