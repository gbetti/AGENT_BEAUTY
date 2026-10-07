import sqlite3
import unittest
from agent import ProductParser, initialize


class AgentTests(unittest.TestCase):
    def test_graph_and_multiple_types(self):
        parser = ProductParser()
        parser.feed('<script type="application/ld+json">{"@graph":[{"@type":["Product","Thing"],"name":"Crema","image":["https://ioma-paris.com/crema.jpg"]}]}</script>')
        self.assertEqual(len(parser.products), 1)
        self.assertEqual(parser.products[0]['name'], 'Crema')

    def test_invalid_json_is_ignored(self):
        parser = ProductParser()
        parser.feed('<script type="application/ld+json">broken</script>')
        self.assertEqual(parser.products, [])

    def test_database_repeatable_initialization(self):
        with sqlite3.connect(':memory:') as db:
            initialize(db)
            initialize(db)
            db.execute('INSERT INTO products(page_url,name,json_ld) VALUES (?,?,?)', ('url', 'Crema', '{}'))
            self.assertEqual(db.execute('SELECT name FROM products').fetchone()[0], 'Crema')
