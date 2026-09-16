# Re:Code Handoff

> `pyeve/cerberus` · 1.3.x · `65e977d` · 커밋 1158개

이 문서는 코드를 설명하지 않는다. **수정 전에 확인해야 할 것**만 모았다.
모든 항목에는 코드 근거가 붙어 있다. 근거가 없는 항목은 만들지 않았다.

## 1. Repository overview

- 저장소: `pyeve/cerberus`
- 기준 커밋: `65e977d` (`1.3.x`)
- 전체 커밋: 1158개

## 3. Questions for the previous developer

1. _insert_logic_error 안의 else 블록에서 자식 에러 자체의 field 대신 상위 에러의 field를 사용하여 메시지를 포맷팅하도록 한 이유가 무엇입니까?
   - 근거: `cerberus/errors.py:594`, `cerberus/errors.py:607`
   - 확인된 사실: _insert_group_error에서는 자식 에러 처리 시 _format_message(child_error.field, child_error)를 호출하는 반면, _insert_logic_error에서는 상위 에러의 필드인 field를 사용하여 _format_message(field, child_error)를 호출하고 있습니다.

2. __normalize_sequence_per_schema에서는 입력 데이터와 스키마의 길이 불일치를 처리하는 검증 로직이 없는 반면, __normalize_sequence_per_items에서는 길이 검증 후 조기 반환하도록 구현된 이유가 무엇인가요?
   - 근거: `cerberus/validator.py:871`, `cerberus/validator.py:873`
   - 확인된 사실: __normalize_sequence_per_schema 함수에서는 len(mapping[field])를 사용하여 동적으로 스키마를 생성하는 반면, __normalize_sequence_per_items 함수에서는 len(rules)와 len(values)를 비교하여 길이가 다를 경우 조기 반환(return)하는 로직이 존재합니다.

3. 키 정규화와 값 정규화 에러 처리에서 _drop_nodes_from_errorpaths에 전달하는 인덱스 목록이 다른 이유는 무엇인가요?
   - 근거: `cerberus/validator.py:826`, `cerberus/validator.py:835`
   - 확인된 사실: 함수 A(__normalize_mapping_per_keysrules)에서는 _drop_nodes_from_errorpaths 호출 시 [2, 4]를 전달하는 반면, 함수 B(__normalize_mapping_per_valuesrules)에서는 [2]만 전달하고 있음

4. _validate_empty와 _validate_nullable에서 _drop_remaining_rules로 전달하는 규칙 목록과 호출 조건의 범위가 다른 이유가 무엇인가요?
   - 근거: `cerberus/validator.py:1371`, `cerberus/validator.py:1376`
   - 확인된 사실: _validate_empty는 비어있는 값일 때 7개의 규칙을 중단하는 반면, _validate_nullable은 값이 None일 때 17개의 규칙을 중단하여 두 검증 함수 간에 생략되는 후속 규칙의 목록과 조건 처리 순서에 차이가 있다.

5. 자식 검증기의 에러 경로를 조정할 때 _validate_keysrules에서는 [2, 4]를 사용하고 _validate_valuesrules에서는 [2]만 사용하는 이유가 무엇인가요?
   - 근거: `cerberus/validator.py:1562`, `cerberus/validator.py:1577`
   - 확인된 사실: _validate_keysrules는 세 번째 인자로 [2, 4]를 전달하여 에러 경로를 조정하는 반면, _validate_valuesrules는 [2]만 전달하고 있다.

## 5. Test evidence gaps

직접 연결된 테스트 근거를 찾지 못했습니다. 테스트가 없다는 뜻은 아니다.

| 파일 | 전체 커밋 |
|---|---|
| `docs/conf.py` | 43 |
| `docs/includes/generate.py` | 7 |

## 6. Dead-code candidates

정적 호출 경로에서 사용 근거를 찾지 못했습니다. 삭제를 권하는 것이 아니라 확인이 필요한 후보다.

| 위치 | 이름 | 종류 | confidence |
|---|---|---|---|
| `cerberus/utils.py:95` | `instance` | variable | 100% |
| `cerberus/utils.py:98` | `instance` | variable | 100% |
| `cerberus/utils.py:101` | `instance` | variable | 100% |
| `cerberus/errors.py:72` | `KEYSCHEMA` | variable | 60% |
| `cerberus/errors.py:73` | `VALUESCHEMA` | variable | 60% |
| `cerberus/errors.py:190` | `is_normalization_error` | property | 60% |
| `cerberus/schema.py:249` | `regenerate_validation_schema` | method | 60% |
| `cerberus/schema.py:331` | `target_schema` | property | 60% |
| `cerberus/schema.py:373` | `_check_with_dependencies` | method | 60% |
| `cerberus/schema.py:389` | `_check_with_items` | method | 60% |

그 외 52개 후보.

## 7. First week

1. 이전 개발자에게 물어볼 것: _insert_logic_error 안의 else 블록에서 자식 에러 자체의 field 대신 상위 에러의 field를 사용하여 메시지를 포맷팅하도록 한 이유가 무엇입니까?
2. `cerberus/utils.py:95` 의 `instance` 이 실제로 쓰이지 않는지 확인한다 (정적 분석으로는 호출 근거를 찾지 못함)
