"""언어별 규칙 한 곳.

함수 추출 · 테스트 파일 판별 · 언어 구성 집계가 모두 여기를 본다.
언어를 늘릴 때 고칠 곳이 여러 파일로 흩어지지 않게 하려고 모았다.

Python 은 표준 `ast` 를 그대로 쓴다(`judge/extract.py`). PHASE 1 에서 검증한 경로라
tree-sitter 로 갈아타면서 같이 흔들 이유가 없다. 나머지 언어만 tree-sitter 로 읽는다.

HTML 은 함수가 없다. 언어 구성 집계와 자주 바뀐 파일(git 기반)에는 들어가지만
함수 쌍 비교 대상은 아니다.
"""

import re
from pathlib import Path

# 원저자의 손이 닿지 않는 코드는 인수인계 질문의 대상이 아니다.
# judge/extract.py 의 EXCLUDE_DIRS 와 같은 목적이며, 언어가 늘어난 만큼 항목도 늘렸다.
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "build", "dist", "out", "target", "bin", "obj",
    "vendor", "third_party", "external", "deps",
    ".tox", ".mypy_cache", "site-packages", "migrations",
    ".next", ".nuxt", "coverage", "Pods", "Debug", "Release",
}

# 최소화·번들 산출물과 타입 선언 파일. 사람이 쓴 구현이 아니라 비교해도 물어볼 게 없다.
# `.d.ts` 뿐 아니라 `.d.cts` · `.d.mts` 도 막는다. axios 실측에서 `index.d.cts` 가
# "자주 바뀐 파일" 1위로 올라왔는데, 선언만 있는 파일이라 확인할 것이 없다.
GENERATED_FILE_RE = re.compile(
    r"(\.min\.(js|css)$|\.bundle\.js$|\.d\.[cm]?ts$|\.g\.cs$|\.designer\.cs$"
    r"|\.pb\.(go|cc|h)$|_pb2\.py$)", re.IGNORECASE)

# 코드가 아닌 파일. 언어 구성의 분모에서 뺀다.
# 빼지 않으면 axios 처럼 문서가 많은 저장소에서 "기타 45.8%" 가 되어
# 코드의 절반을 못 본 것처럼 읽힌다. 실제로는 전부 md · json 이었다.
NON_CODE_EXTS = {
    ".md", ".markdown", ".rst", ".txt", ".adoc",
    ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".xml", ".lock", ".env",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".woff", ".woff2", ".ttf",
    ".csv", ".tsv", ".pdf", ".zip", ".gz", ".map", ".snap", ".patch", ".log",
}


class Language:
    """한 언어를 분석하는 데 필요한 규칙 묶음."""

    def __init__(self, key, label, exts, grammar=None, nodes=(), analyzable=True):
        self.key = key
        self.label = label              # 화면에 보여줄 이름
        self.exts = exts                # 이 언어로 볼 확장자
        self.grammar = grammar          # tree-sitter 문법 이름. None 이면 ast(Python)
        self.nodes = frozenset(nodes)   # 함수로 볼 노드 타입
        self.analyzable = analyzable    # 함수 쌍 비교 대상인가


# 노드 타입은 추측하지 않고 각 문법으로 직접 파싱해 확인한 값이다.
LANGUAGES = [
    Language("python", "Python", {".py", ".pyi"}),
    Language("java", "Java", {".java"}, "java",
             ("method_declaration", "constructor_declaration")),
    Language("csharp", "C#", {".cs"}, "csharp",
             ("method_declaration", "constructor_declaration", "local_function_statement")),
    Language("cpp", "C++", {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}, "cpp",
             ("function_definition",)),
    Language("c", "C", {".c", ".h"}, "c", ("function_definition",)),
    # function_expression 을 빼먹으면 `module.exports = function (grunt) {}` 이나
    # `var f = function () {}` 같은 CommonJS 스타일이 통째로 사라진다.
    # django 의 JS 파일 감사에서 176개를 놓치고 있었다.
    Language("typescript", "TypeScript", {".ts", ".mts", ".cts"}, "typescript",
             ("function_declaration", "method_definition", "arrow_function",
              "function_expression", "generator_function_declaration")),
    Language("tsx", "TypeScript (TSX)", {".tsx"}, "tsx",
             ("function_declaration", "method_definition", "arrow_function",
              "function_expression", "generator_function_declaration")),
    Language("javascript", "JavaScript", {".js", ".jsx", ".mjs", ".cjs"}, "javascript",
             ("function_declaration", "method_definition", "arrow_function",
              "function_expression", "generator_function_declaration")),
    # 함수가 없으므로 구성 집계에만 쓴다.
    Language("html", "HTML", {".html", ".htm"}, analyzable=False),
]

BY_KEY = {lang.key: lang for lang in LANGUAGES}
BY_EXT = {ext: lang for lang in LANGUAGES for ext in lang.exts}

# 함수 쌍 비교가 가능한 언어. 리포트 문구에서도 쓴다.
ANALYZABLE = [lang for lang in LANGUAGES if lang.analyzable]

# production 코드가 아닌 파일이 들어 있는 흔한 디렉터리 이름.
# 스토리북 스토리·예제·목업은 "일부러 다르게 만든" 코드라 서로 비교하면
# `PopoverNonModal` 과 `PopoverFullyModal` 의 차이를 묻는 무의미한 질문이 나온다
# (radix-ui/primitives 실측: 후보 200개 중 99개가 stories 파일이었다).
# 다음 개발자가 실제로 고칠 코드만 대상으로 한다.
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing",
             "stories", "storybook", "__mocks__", "__fixtures__", "fixtures", "mocks"}

# 언어별 테스트 파일 이름 규칙. Java 의 `FooTest.java`, JS 의 `foo.spec.ts` 처럼 제각각이다.
TEST_NAME_RE = re.compile(
    r"(^test_"                       # test_foo.py, test_foo.c
    r"|_test\.[a-z]+$"               # foo_test.py, foo_test.go
    r"|^conftest\.py$"
    r"|Tests?\.(java|cs|kt)$"        # FooTest.java, FooTests.cs
    r"|^Test[A-Z]"                   # TestFoo.java
    r"|\.(test|spec)\.[a-z]+$"       # foo.test.ts, foo.spec.js
    r"|\.(stories|story)\.[a-z]+$"   # foo.stories.tsx  (스토리북 예제)
    r")", re.IGNORECASE)


def detect(rel_path) -> Language | None:
    """경로의 확장자로 언어를 정한다. 모르는 확장자는 None."""
    return BY_EXT.get(Path(rel_path).suffix.lower())


def is_excluded(rel_path) -> bool:
    """분석에서 빼는 경로인가. 의존성·빌드 산출물·생성 파일."""
    rel = Path(rel_path)
    if not EXCLUDE_DIRS.isdisjoint(rel.parts):
        return True
    return bool(GENERATED_FILE_RE.search(rel.name))


def is_test_file(rel_path) -> bool:
    """테스트 파일인가. 언어와 무관하게 이름 규칙과 디렉터리 이름으로 본다."""
    rel = Path(rel_path)
    if TEST_NAME_RE.search(rel.name):
        return True
    return any(part.lower() in TEST_DIRS for part in rel.parts[:-1])


# `.h` 는 C 와 C++ 가 같이 쓴다. 확장자만으로는 못 가른다.
CPP_MARKERS = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}


def header_language(clone_path: Path) -> Language:
    """이 저장소에서 `.h` 를 어느 언어로 볼지 정한다.

    저장소에 C++ 파일이 하나라도 있으면 `.h` 도 C++ 로 본다. spdlog 처럼
    헤더만으로 이뤄진 C++ 라이브러리가 흔한데, `.h` 를 무조건 C 로 보면
    C++ 코드 1,015개가 "C" 로 집계된다(실측). 반대로 순수 C 저장소에서
    `.h` 를 C++ 로 보면 cJSON 이 "C++ 프로젝트" 로 표시된다.
    C++ 문법은 C 의 상위집합이라 잘못 골라도 파싱 자체는 통과하지만,
    보고서의 언어 구성이 틀리면 읽는 사람이 오해한다.
    """
    for path in clone_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in CPP_MARKERS:
            if not is_excluded(path.relative_to(clone_path).as_posix()):
                return BY_KEY["cpp"]
    return BY_KEY["c"]


def iter_source_files(clone_path: Path, header_lang: Language | None = None):
    """분석 대상 소스 파일을 (경로, 상대경로, 언어)로 돌려준다."""
    header_lang = header_lang or header_language(clone_path)
    for path in clone_path.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(clone_path).as_posix()
        if is_excluded(rel):
            continue
        lang = detect(rel)
        if lang is None:
            continue
        if path.suffix.lower() == ".h":
            lang = header_lang
        yield path, rel, lang


def source_line_count(clone_path: Path) -> int:
    """분석 대상 소스의 전체 줄 수.

    "저장소에서 얼마나 나갔는가" 를 비율로 보여줄 때 분모로 쓴다.
    문서·설정은 애초에 분석 대상이 아니므로 세지 않는다.
    """
    total = 0
    for path, _, lang in iter_source_files(clone_path):
        if not lang.analyzable:
            continue
        try:
            total += path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        except OSError:
            continue
    return total


def composition(clone_path: Path) -> list[dict]:
    """저장소의 언어 구성. 파일 수 기준 내림차순.

    결과가 얇을 때 "확인할 게 없어서"인지 "그 언어를 안 봐서"인지 구분해 주기 위한 값이다.
    """
    counted: dict[str, int] = {}
    other = 0
    header_lang = header_language(clone_path)
    for path in clone_path.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(clone_path).as_posix()
        if is_excluded(rel):
            continue
        lang = detect(rel)
        if lang is None:
            # 문서·설정·이미지는 코드가 아니므로 분모에서 뺀다.
            if Path(rel).suffix.lower() in NON_CODE_EXTS or not Path(rel).suffix:
                continue
            other += 1
        else:
            # `.h` 는 저장소 성격에 따라 C 인지 C++ 인지 갈린다.
            if path.suffix.lower() == ".h":
                lang = header_lang
            counted[lang.key] = counted.get(lang.key, 0) + 1

    total = sum(counted.values()) + other
    if not total:
        return []

    rows = [{"key": key, "label": BY_KEY[key].label, "files": n,
             "percent": round(n * 100 / total, 1),
             "analyzed": BY_KEY[key].analyzable}
            for key, n in counted.items()]
    rows.sort(key=lambda r: -r["files"])
    if other:
        rows.append({"key": "other", "label": "그 외 언어", "files": other,
                     "percent": round(other * 100 / total, 1), "analyzed": False})
    return rows


# ---------------------------------------------------------------- tree-sitter

_PARSERS: dict[str, object] = {}


def parser_for(lang: Language):
    """문법별 파서를 한 번만 만들어 재사용한다. 매번 만들면 느리다."""
    if lang.grammar not in _PARSERS:
        from tree_sitter_language_pack import get_parser
        _PARSERS[lang.grammar] = get_parser(lang.grammar)
    return _PARSERS[lang.grammar]


def _name_of(node, src: bytes) -> str | None:
    """함수 이름. 언어마다 붙어 있는 자리가 달라 세 경로를 다 본다."""
    field = node.child_by_field_name("name")
    if field is not None:
        return src[field.start_byte:field.end_byte].decode("utf-8", "replace")

    # C/C++ 은 이름이 declarator 안쪽에 있다. 포인터 반환이면 한 겹 더 들어간다.
    node_ = node.child_by_field_name("declarator")
    while node_ is not None:
        if node_.type in ("identifier", "field_identifier", "qualified_identifier",
                          "operator_name", "destructor_name"):
            return src[node_.start_byte:node_.end_byte].decode("utf-8", "replace")
        nxt = node_.child_by_field_name("declarator")
        if nxt is None:
            for child in node_.children:
                if child.type in ("identifier", "field_identifier", "qualified_identifier"):
                    return src[child.start_byte:child.end_byte].decode("utf-8", "replace")
        node_ = nxt

    # JS/TS 화살표 함수는 스스로 이름이 없다. 대입된 변수 이름을 쓴다.
    parent = node.parent
    if parent is not None and parent.type in ("variable_declarator", "pair",
                                              "assignment_expression", "public_field_definition"):
        field = (parent.child_by_field_name("name")
                 or parent.child_by_field_name("key")
                 or parent.child_by_field_name("left"))
        if field is not None:
            return src[field.start_byte:field.end_byte].decode("utf-8", "replace")
    return None


def _signature_of(node, src: bytes, name: str | None = None) -> str:
    """선언부만 잘라 시그니처로 쓴다. 본문 시작 전까지가 선언부다."""
    body = node.child_by_field_name("body")
    end = body.start_byte if body is not None else node.end_byte
    text = src[node.start_byte:end].decode("utf-8", "replace")
    sig = re.sub(r"\s+", " ", text).strip().rstrip("{=>").strip()
    # 화살표 함수는 노드가 `(` 부터 시작해서 이름이 빠진다. 보고서에서 어느 함수인지
    # 알아볼 수 없으므로 대입된 변수 이름을 앞에 붙인다.
    # 이름이 이미 어딘가 들어 있으면 붙이지 않는다. 첫 괄호 앞만 보면 안 된다 -
    # Java 의 `@SuppressWarnings("...") public static ... newFactory(` 처럼
    # 어노테이션이 먼저 괄호를 열면 이름을 못 찾고 중복해서 붙인다.
    if name and name not in sig:
        sig = f"{name} = {sig}"
    return sig


# 파일 밖에서 부를 수 없게 만드는 표시. 이런 함수는 자기 파일만 뒤지면
# 쓰이는지 아닌지가 확정된다. 저장소 전체를 훑어 "아마 안 쓰일 것" 이라고 추측할 필요가 없다.
# Java 는 modifier 를 생략하면 package-private 이라 같은 패키지의 다른 파일에서 보인다.
# 그래서 명시적 `private` 만 파일 한정으로 본다.
# C 계열은 `static` 이 파일 스코프다.
FILE_LOCAL_MARKER = {
    "java": re.compile(r"\bprivate\b"),
    "c": re.compile(r"\bstatic\b"),
    "cpp": re.compile(r"\bstatic\b"),
}

# C# 은 접근 제어자를 생략하면 기본이 private 이다. 명시적 `private` 만 세면
# serilog 1,538개 중 1개만 잡힌다(실측). 공개 제어자가 하나도 없으면 private 로 본다.
CSHARP_PUBLIC_RE = re.compile(r"\b(public|protected|internal)\b")

# JS/TS 는 modifier 가 아니라 export 문으로 공개된다. 조상에 export 가 있으면 파일 밖에서 쓸 수 있다.
_EXPORT_NODES = {"export_statement", "export_specifier"}


def _is_file_local(node, lang: Language, signature: str, name: str) -> bool:
    """이 함수가 자기 파일 밖에서 호출될 수 있는가를 뒤집어 판단한다."""
    if lang.key == "csharp":
        # 인터페이스 멤버는 제어자가 없어도 public 이다. 이걸 빼먹으면 serilog 의
        # ILogger.cs 같은 인터페이스 파일이 통째로 후보로 올라온다(실측 30건 중 다수).
        parent = node.parent
        while parent is not None:
            if parent.type == "interface_declaration":
                return False
            parent = parent.parent
        return not CSHARP_PUBLIC_RE.search(signature)

    if lang.key == "cpp":
        # C++ 의 `static` 은 자리에 따라 뜻이 다르다. 네임스페이스 수준이면 파일 스코프지만
        # 클래스 안이면 공개 static 멤버다. spdlog 의 `class mdc { public: static void put(...) }`
        # 가 파일 한정으로 잡혀 공개 API 가 미사용 후보로 올라왔다(실측).
        parent = node.parent
        while parent is not None:
            if parent.type in ("class_specifier", "struct_specifier", "union_specifier"):
                return False
            parent = parent.parent
        return bool(FILE_LOCAL_MARKER["cpp"].search(signature))

    marker = FILE_LOCAL_MARKER.get(lang.key)
    if marker is not None:
        return bool(marker.search(signature))

    if lang.key in ("javascript", "typescript", "tsx"):
        if not name.isidentifier():
            # `module.exports.foo = ...`, `resolvers[type] = ...` 같은 형태.
            # 이름이 식별자가 아니라 참조 수를 세는 규칙이 통하지 않는다.
            return False
        # 그 자리에서 바로 넘기는 함수는 정의가 곧 사용이다.
        # `JSON.stringify(obj, function replacer(k, v) {...})` 가 대표적인데,
        # 이걸 안 거르면 axios 한 곳에서만 후보가 207건 나온다(실측).
        # 선언문이거나 변수에 대입된 것만 "부르는 자리가 따로 있어야 하는" 함수다.
        if node.type != "function_declaration":
            if node.parent is None or node.parent.type != "variable_declarator":
                return False
        parent = node.parent
        while parent is not None:
            if parent.type in _EXPORT_NODES:
                return False
            parent = parent.parent
        return True

    return False


def _count_statements(body) -> int:
    """본문의 문장 수. 빈 함수와 한 줄짜리 getter 를 걸러내는 용도다.

    Python 쪽 `ast` 계산과 정확히 같은 수를 낼 필요는 없다. 하한이 1 이라
    "비어 있는가"만 구분되면 된다.
    """
    if body is None:
        return 0
    count, stack = 0, [body]
    while stack:
        node = stack.pop()
        for child in node.named_children:
            if child.type.endswith(("statement", "declaration")):
                count += 1
            stack.append(child)
    # 화살표 함수처럼 본문이 식 하나인 경우도 비어 있는 것은 아니다.
    return count or (1 if body.named_child_count else 0)


def _leading_comment(node, src: bytes) -> str | None:
    """함수 바로 위에 붙은 주석. Python 독스트링 자리에 해당한다."""
    prev = node.prev_sibling
    # 접근 제어자 등이 앞에 붙으면 주석이 부모 쪽에 달린다.
    if prev is None and node.parent is not None:
        prev = node.parent.prev_sibling
    if prev is None or prev.type not in ("comment", "line_comment", "block_comment"):
        return None
    text = src[prev.start_byte:prev.end_byte].decode("utf-8", "replace").strip()
    return text or None


# 이름이 실제로 쓰인 자리를 셀 때 볼 노드. 주석과 문자열은 식별자가 아니라 여기 안 잡힌다.
IDENTIFIER_NODES = frozenset({
    "identifier", "field_identifier", "property_identifier", "type_identifier",
    "shorthand_property_identifier", "shorthand_property_identifier_pattern",
    "statement_identifier", "namespace_identifier",
})


def has_parse_error(text: str, lang: Language) -> bool:
    """이 파일이 문법대로 깔끔하게 읽혔는가.

    tree-sitter 는 실패해도 예외를 내지 않고 ERROR 노드를 섞은 트리를 돌려준다.
    그 트리로 "이 함수는 아무 데서도 안 쓰인다" 같은 단정을 하면 근거가 틀린 자리를
    가리킨다. 매크로가 많은 C++ 헤더와 `#if` 가 있는 C# 파일에서 실제로 겪었다.
    """
    return parser_for(lang).parse(text.encode("utf-8")).root_node.has_error


def identifier_counts(text: str, lang: Language) -> dict[str, int]:
    """파일 안에서 각 이름이 식별자로 몇 번 나오는지 센다.

    정규식으로 세면 안 된다. 주석과 문자열을 정규식으로 지우려다
    `/["']/` 같은 정규식 리터럴 안의 따옴표를 문자열 시작으로 오인해
    119줄 파일이 74줄로 줄고 함수 정의 줄이 통째로 사라진 적이 있다(axios 실측).
    그러면 "정의 말고는 안 나온다" 가 되어 멀쩡한 함수가 미사용으로 잡힌다.
    """
    src = text.encode("utf-8")
    tree = parser_for(lang).parse(src)
    counts: dict[str, int] = {}
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in IDENTIFIER_NODES:
            name = src[node.start_byte:node.end_byte].decode("utf-8", "replace")
            counts[name] = counts.get(name, 0) + 1
        stack.extend(node.named_children)
    return counts


def extract_functions(text: str, rel: str, lang: Language, commit_count: int) -> list[dict]:
    """tree-sitter 로 함수를 뽑는다. 반환 형식은 `judge/extract.py` 와 같다."""
    src = text.encode("utf-8")
    tree = parser_for(lang).parse(src)
    lines = text.splitlines()
    is_test = is_test_file(rel)

    out, stack = [], [tree.root_node]
    while stack:
        node = stack.pop()
        stack.extend(node.named_children)
        if node.type not in lang.nodes:
            continue

        name = _name_of(node, src)
        if not name:
            # 이름 없는 콜백(`arr.map(x => x * 2)`)은 인수인계 질문 대상이 아니다.
            # 이름이 있어야 "이전 개발자에게 어디를 물어볼지" 가리킬 수 있다.
            continue

        start, end = node.start_point[0] + 1, node.end_point[0] + 1
        signature = _signature_of(node, src, name)
        out.append({
            "file": rel,
            "name": name,
            "start_line": start,
            "end_line": end,
            "source": "\n".join(lines[start - 1:end]),
            "signature": signature[:200],
            "docstring": _leading_comment(node, src),
            "commit_count": commit_count,
            "is_test": is_test,
            "lang": lang.key,
            "body_statements": _count_statements(node.child_by_field_name("body")),
            # 파일 밖에서 부를 수 없는 함수. 사용 근거 확인(16.2)이 여기서만 확정된다.
            "file_local": _is_file_local(node, lang, signature, name),
        })
    return out
