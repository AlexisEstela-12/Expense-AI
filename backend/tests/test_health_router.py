"""Offline checks for the first extracted API router."""

import sys
import unittest

from fastapi import FastAPI
from fastapi.routing import APIRoute

from api.routers.health import health, router


class HealthRouterTest(unittest.TestCase):
    def test_health_route_and_response_without_importing_main(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(router)

        routes = [route for route in router.routes if isinstance(route, APIRoute)]
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].path, '/health')
        self.assertEqual(routes[0].methods, {'GET'})
        self.assertEqual(routes[0].status_code, None)  # FastAPI default: 200
        self.assertIsNone(routes[0].response_model)
        self.assertEqual(health(), {'status': 'ok'})
        self.assertEqual(routes[0].endpoint(), {'status': 'ok'})

        operation = app.openapi()['paths']['/health']['get']
        self.assertEqual(set(operation['responses']), {'200'})
        self.assertEqual(operation['operationId'], 'health_health_get')


if __name__ == '__main__':
    unittest.main()
