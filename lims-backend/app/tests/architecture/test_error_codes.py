"""Chặn nợ mã lỗi (M-05/T1.3).

153 mã lỗi từng là chuỗi literal rải rác ở 359 điểm. Không compiler nào kiểm nội
dung chuỗi, nên gõ sai một ký tự đi thẳng ra production; và không ai tra được mã
nào đã chết hay đã có mã cùng nghĩa chưa.

Xem MAINTAINABILITY_PLAN.md §T1.3 và CONTRIBUTING.md §3.
"""
import ast
import json
import pathlib

from app.core.error_codes import ErrorCode

# Factory nhận mã lỗi làm tham số đầu tiên.
_FACTORIES = {"AppException", "conflict", "unprocessable"}

_APP_DIR = pathlib.Path(__file__).resolve().parents[2]


def _source_files():
    for p in sorted(_APP_DIR.rglob("*.py")):
        if "tests" in p.parts or p.name == "error_codes.py":
            continue
        yield p


def _raw_code_literals():
    """Trả [(file, dòng, mã)] cho mọi lời gọi factory dùng chuỗi thô."""
    out = []
    for p in _source_files():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — file hỏng thì lint bắt trước
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
            if name not in _FACTORIES:
                continue
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value.isupper()
            ):
                out.append((p.relative_to(_APP_DIR.parent), first.lineno, first.value))
    return out


def test_no_raw_error_code_strings():
    """Mã lỗi phải dùng ErrorCode.X, không phải chuỗi literal."""
    offenders = _raw_code_literals()
    assert not offenders, (
        f"{len(offenders)} chỗ còn dùng chuỗi thô làm mã lỗi. Dùng ErrorCode:\n"
        + "\n".join(f"  {f}:{ln} → ErrorCode.{c}" for f, ln, c in offenders[:30])
    )


def test_enum_value_equals_name():
    """Giá trị phải bằng tên.

    Lệch nhau là bẫy: đọc code thấy một đằng, client nhận một nẻo.
    """
    bad = [(m.name, m.value) for m in ErrorCode if m.name != m.value]
    assert not bad, f"Mã có giá trị khác tên: {bad}"


def test_errorcode_is_str_compatible():
    """Kế thừa str để mọi so sánh chuỗi cũ và JSON serialize giữ nguyên hành vi.

    Mất tính chất này là phá vỡ hợp đồng API một cách im lặng: response vẫn 200/4xx
    như cũ nhưng trường `code` đổi thành "ErrorCode.X".
    """
    assert ErrorCode.VALIDATION_ERROR == "VALIDATION_ERROR"
    assert json.dumps({"code": ErrorCode.VALIDATION_ERROR}) == '{"code": "VALIDATION_ERROR"}'


def test_merged_alias_is_gone():
    """DEPT_NOT_FOUND đã gộp vào DEPARTMENT_NOT_FOUND — không được quay lại."""
    assert not hasattr(ErrorCode, "DEPT_NOT_FOUND"), (
        "DEPT_NOT_FOUND trùng nghĩa với DEPARTMENT_NOT_FOUND, đã gộp ở T1.3."
    )


def test_every_code_is_screaming_snake_case():
    """Định dạng lệch làm mã khó grep và khó đối chiếu với frontend.

    CỐ Ý không parametrize theo từng mã: 153 test case cho một luật định dạng chỉ
    làm phồng số liệu test mà không thêm thông tin nào.
    """
    bad = [
        m.name
        for m in ErrorCode
        if not m.name.replace("_", "").isalnum()
        or m.name.upper() != m.name
        or m.name.startswith("_")
    ]
    assert not bad, f"Mã sai định dạng SCREAMING_SNAKE_CASE: {bad}"
