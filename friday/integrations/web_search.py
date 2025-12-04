"""
Web Search Integration for Jarvis
"""
import os
import requests
from typing import List, Dict, Optional
from friday.utils.logger import get_logger

logger = get_logger("web_search")


class SearchResult:
    """Represents a search result"""
    def __init__(self, title: str, url: str, snippet: str):
        self.title = title
        self.url = url
        self.snippet = snippet

    def __str__(self):
        return f"{self.title}: {self.snippet[:100]}..."

    def to_dict(self):
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet
        }


class WebSearchService:
    """Web search integration service"""

    def __init__(self):
        self.enabled = True
        # Try to load API keys if available
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self.serp_api_key = os.getenv("SERPAPI_KEY", "")

        logger.info("Web Search service initialized")

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Search the web and return results

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects
        """
        # Try Tavily first if API key available
        if self.tavily_api_key:
            results = self._search_tavily(query, max_results)
            if results:
                return results

        # Fall back to DuckDuckGo (no API key needed)
        return self._search_duckduckgo(query, max_results)

    def _search_tavily(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using Tavily API"""
        try:
            import tavily
            client = tavily.TavilyClient(api_key=self.tavily_api_key)

            response = client.search(query=query, max_results=max_results)

            results = []
            for item in response.get('results', []):
                results.append(SearchResult(
                    title=item.get('title', ''),
                    url=item.get('url', ''),
                    snippet=item.get('content', '')
                ))

            logger.info(f"Tavily search: found {len(results)} results for '{query}'")
            return results

        except ImportError:
            logger.debug("Tavily library not installed")
            return []
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []

    def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using DuckDuckGo (no API key needed)"""
        try:
            # Use DuckDuckGo instant answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1,
                "skip_disambig": 1
            }

            response = requests.get(url, params=params, timeout=5)
            data = response.json()

            results = []

            # Get abstract if available
            if data.get('Abstract'):
                results.append(SearchResult(
                    title=data.get('Heading', query),
                    url=data.get('AbstractURL', ''),
                    snippet=data['Abstract']
                ))

            # Get related topics
            for topic in data.get('RelatedTopics', [])[:max_results-1]:
                if 'Text' in topic:
                    results.append(SearchResult(
                        title=topic.get('Text', '').split(' - ')[0] if ' - ' in topic.get('Text', '') else query,
                        url=topic.get('FirstURL', ''),
                        snippet=topic.get('Text', '')
                    ))

            logger.info(f"DuckDuckGo search: found {len(results)} results for '{query}'")
            return results

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []

    def search_and_summarize(self, query: str, openai_client=None) -> str:
        """
        Search and return AI-summarized results

        Args:
            query: Search query
            openai_client: OpenAI client for summarization

        Returns:
            Summarized search results as string
        """
        results = self.search(query, max_results=5)

        if not results:
            return f"No results found for '{query}'"

        # If no AI client, return plain text results
        if not openai_client:
            output = f"Search results for '{query}':\n\n"
            for i, result in enumerate(results, 1):
                output += f"{i}. {result.title}\n{result.snippet[:200]}...\n\n"
            return output.strip()

        # Use AI to summarize
        try:
            results_text = "\n\n".join([
                f"Source {i}: {result.title}\n{result.snippet}"
                for i, result in enumerate(results, 1)
            ])

            prompt = f"""Based on these search results, provide an ULTRA BRIEF summary in ONE SENTENCE ONLY answering: "{query}"

Search Results:
{results_text}

ONE SENTENCE summary:"""

            messages = [{"role": "user", "content": prompt}]
            summary = openai_client.chat_completion(messages)

            return summary

        except Exception as e:
            logger.error(f"Error summarizing results: {e}")
            # Fall back to plain text
            output = f"Search results for '{query}':\n\n"
            for i, result in enumerate(results, 1):
                output += f"{i}. {result.title}\n{result.snippet[:150]}...\n\n"
            return output.strip()

    def get_quick_answer(self, query: str) -> Optional[str]:
        """
        Get quick answer for simple queries (like "what time is it", "weather", etc.)

        Args:
            query: Simple query

        Returns:
            Quick answer string or None
        """
        try:
            # Use DuckDuckGo instant answer
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_redirect": 1,
                "no_html": 1
            }

            response = requests.get(url, params=params, timeout=5)
            data = response.json()

            # Check for instant answer
            if data.get('Answer'):
                return data['Answer']

            if data.get('Abstract'):
                return data['Abstract']

            return None

        except Exception as e:
            logger.error(f"Quick answer error: {e}")
            return None
