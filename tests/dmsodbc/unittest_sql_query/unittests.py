#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from dmsodbc import _build_sql_or_query


class TestDmsOdbcSql(unittest.TestCase):
    """Test that the SQL string methods behave correctly.
    """

    def test_or_query(self):
        """ Tests that the _build_sql_or_query method behaves correctly.
        """
        name = "id"
        values = ["1", "2", "3"]
        sql = _build_sql_or_query(name, values)
        self.assertEquals(sql, "id = '1' or id = '2' or id = '3'")
        self.assertRaises(ValueError, _build_sql_or_query, name, [])
        self.assertRaises(ValueError, _build_sql_or_query, name, None)
        self.assertRaises(ValueError, _build_sql_or_query, None, values)
        self.assertRaises(ValueError, _build_sql_or_query, "", values)


if __name__ == '__main__':
    unittest.main()
