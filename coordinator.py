"""Run three specialized Python agents with one shared campaign brief."""
from datetime import datetime, timezone

from agents.assets import AssetsAgent
from agents.keywords import KeywordAgent
from agents.trends import TrendAgent
from catalog import load_products


class AgentExecutionError(RuntimeError):
    def __init__(self, agent_name, cause, pipeline):
        self.agent_name = agent_name
        self.pipeline = pipeline
        super().__init__(f'{agent_name}: {cause}')


class BeautyCoordinator:
    """Dependencies can be replaced independently without changing the CLI."""
    def __init__(self, trend_agent=None, keyword_agent=None, assets_agent=None):
        self.trend_agent = trend_agent if trend_agent is not None else TrendAgent()
        self.keyword_agent = keyword_agent if keyword_agent is not None else KeywordAgent()
        self.assets_agent = assets_agent if assets_agent is not None else AssetsAgent()

    def run(self, args, *, now=None, progress=None):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError('Il coordinatore richiede una data con fuso orario.')
        products = load_products(args.database)
        pipeline = {'schema_version': 1, 'execution_mode': 'specialized_python_agents',
                    'created_at': now.isoformat(), 'stages': [
                        {'agent': 'trends', 'name': 'Trend Beauty', 'status': 'pending'},
                        {'agent': 'keywords', 'name': 'Keyword & Domanda', 'status': 'pending'},
                        {'agent': 'assets', 'name': 'Creative Studio', 'status': 'pending'}]}

        def stage(identifier, name, action):
            record = next(item for item in pipeline['stages'] if item['agent'] == identifier)
            record.update(status='running', started_at=datetime.now(timezone.utc).isoformat())
            if progress:
                progress(identifier, 'running')
            try:
                result = action()
            except Exception as error:
                record.update(status='failed', finished_at=datetime.now(timezone.utc).isoformat(),
                              error=str(error))
                if progress:
                    progress(identifier, 'failed')
                raise AgentExecutionError(name, error, pipeline) from error
            record.update(status='completed', finished_at=datetime.now(timezone.utc).isoformat())
            if progress:
                progress(identifier, 'completed')
            return result

        trends = stage('trends', 'Trend Beauty',
                       lambda: self.trend_agent.run(products, args, now))
        keywords = stage('keywords', 'Keyword & Domanda',
                         lambda: self.keyword_agent.run(trends, now))
        return stage('assets', 'Creative Studio',
                     lambda: self.assets_agent.run(trends, keywords, args, now, pipeline))
