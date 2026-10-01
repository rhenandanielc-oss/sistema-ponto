import pytest

from app.schemas.employee import normalize_cpf


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("529.982.247-25", "52998224725"), ("11144477735", "11144477735"), ("", None), (None, None)],
)
def test_valid_cpf(raw: str | None, expected: str | None) -> None:
    assert normalize_cpf(raw) == expected


@pytest.mark.parametrize("raw", ["529.982.247-26", "111.111.111-11", "123", "1234567890123"])
def test_invalid_cpf(raw: str) -> None:
    with pytest.raises(ValueError, match="CPF"):
        normalize_cpf(raw)
