"""Offline checks for the extracted categories router."""

import sys
import unittest

from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.routers.categories import create_router
from db.base import Base
from db.models import Category
from schemas.categories import CategoryIn


class CategoriesRouterTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)

        def db():
            yield self.session

        self.db = db
        self.router = create_router(db)
        self.routes = {
            (route.path, next(iter(route.methods))): route
            for route in self.router.routes if isinstance(route, APIRoute)
        }

    def test_routes_keep_paths_methods_status_and_dependency(self):
        self.assertNotIn('main', sys.modules)
        self.assertNotIn('db.session', sys.modules)
        self.assertEqual(set(self.routes), {
            ('/categories', 'GET'), ('/categories', 'POST'),
        })
        self.assertIsNone(self.routes[('/categories', 'GET')].status_code)
        self.assertEqual(self.routes[('/categories', 'POST')].status_code, 201)
        for route in self.routes.values():
            self.assertIs(route.dependant.dependencies[0].call, self.db)
        app = FastAPI(title='Expense AI API', version='0.1.0')
        app.include_router(self.router)
        paths = app.openapi()['paths']['/categories']
        self.assertEqual(set(paths), {'get', 'post'})
        self.assertEqual(set(paths['get']['responses']), {'200'})
        self.assertEqual(set(paths['post']['responses']), {'201', '422'})

    def test_get_categories_keeps_kind_and_name_order(self):
        self.session.add_all([
            Category(name='Zeta', kind='expense'),
            Category(name='Sueldo', kind='income'),
            Category(name='Alimentación', kind='expense'),
        ])
        self.session.commit()
        result = self.routes[('/categories', 'GET')].endpoint(session=self.session)
        self.assertEqual([(item['kind'], item['name']) for item in result], [
            ('expense', 'Alimentación'), ('expense', 'Zeta'), ('income', 'Sueldo'),
        ])
        self.assertTrue(all(isinstance(item['id'], int) for item in result))

    def test_create_trims_name_and_rejects_duplicate_in_same_kind(self):
        create = self.routes[('/categories', 'POST')].endpoint
        result = create(CategoryIn(name='  Servicios  ', kind='expense'), session=self.session)
        self.assertEqual(result, {
            'id': result['id'], 'name': 'Servicios', 'kind': 'expense',
        })
        with self.assertRaises(HTTPException) as duplicate:
            create(CategoryIn(name='Servicios', kind='expense'), session=self.session)
        self.assertEqual(duplicate.exception.status_code, 409)
        self.assertEqual(duplicate.exception.detail, 'Esta categoría ya existe.')
        other_kind = create(CategoryIn(name='Servicios', kind='income'), session=self.session)
        self.assertEqual(other_kind['kind'], 'income')

    def test_blank_name_and_schema_validation(self):
        create = self.routes[('/categories', 'POST')].endpoint
        with self.assertRaises(HTTPException) as blank:
            create(CategoryIn(name='   ', kind='expense'), session=self.session)
        self.assertEqual(blank.exception.status_code, 400)
        self.assertEqual(blank.exception.detail, 'La categoría no puede estar vacía.')
        with self.assertRaises(ValidationError):
            CategoryIn.model_validate({'name': '', 'kind': 'expense'})
        with self.assertRaises(ValidationError):
            CategoryIn.model_validate({'name': 'Servicios', 'kind': 'other'})


if __name__ == '__main__':
    unittest.main()
