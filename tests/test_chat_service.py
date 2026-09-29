import pytest
from app.services.chat import ask_chat_assistant, _rule_based_fallback


@pytest.mark.asyncio
async def test_chat_rule_based_fallback():
    ctx = {
        "transaction_type": "837P",
        "sender_id": "SUBMITTER1",
        "receiver_id": "PAYER1",
        "valid": False,
        "errors": [{"code": "ERR01", "message": "Missing NPI", "segment": "NM1"}],
    }

    ans_type = await ask_chat_assistant("What transaction type is this?", ctx)
    assert "837P" in ans_type

    ans_err = await ask_chat_assistant("Are there any errors?", ctx)
    assert "Missing NPI" in ans_err or "1 validation issues" in ans_err

    ans_partner = await ask_chat_assistant("Who are the trading partners?", ctx)
    assert "SUBMITTER1" in ans_partner
    assert "PAYER1" in ans_partner
