from langchain.agents import create_agent

from src.agents.models import gemini_flash
from src.agents.schema import ArticleSummary
from src.models.schema import Article

SYSTEM_PROMPT = """
You are an expert news summarizer.
You will be given a single news article and your task is to summarize it in a
concise and informative manner. Your summary should capture the main points of
the article, including key details and context, and be clear, accurate, and
easy to understand. Make sure to give the summary and keypoints in the orignal
language of the article. Avoid adding any personal opinions or interpretations.

Respond with:
- summary: a concise 2-3 sentence summary of the article.
- topic: the single most relevant topic tag for the article, chosen from:
  Politics, Economy, Sports, Entertainment, Technology, Health, Science,
  World, Local.
- key_points: 3 to 5 short bullet points covering the most important facts.
"""


def create_summarize_agent():
    return create_agent(
        model=gemini_flash,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ArticleSummary,
    )


def summarize_articles(articles: list[Article]) -> list[ArticleSummary]:
    agent = create_summarize_agent()

    inputs = [
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"Summarize the following news article.\n\n"
                    f"Title: {article.title}\n\n{article.text}",
                }
            ]
        }
        for article in articles
    ]

    results = agent.batch(inputs)
    return [result["structured_response"] for result in results]
