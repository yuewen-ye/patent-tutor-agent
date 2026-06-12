from langchain_core.prompts import ChatPromptTemplate

from backend.app.agents.common import messages_from_prompt


def test_messages_from_prompt_maps_langchain_roles_to_chat_api_roles() -> None:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "system text"),
            ("human", "hello {name}"),
            ("ai", "assistant text"),
        ]
    )

    messages = messages_from_prompt(prompt, name="learner")

    assert [message.role for message in messages] == ["system", "user", "assistant"]
    assert [message.content for message in messages] == [
        "system text",
        "hello learner",
        "assistant text",
    ]
