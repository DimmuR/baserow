from django.db import connection

import pytest

from baserow.contrib.database.fields.field_converters import LinkRowFieldConverter
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import LinkRowField
from baserow.contrib.database.fields.registries import field_type_registry


def _create_invalid_jsonb_lookup_field(data_fixture):
    """
    Builds a lookup field whose physical column is `jsonb` (array formula type) and
    then invalidates it by converting its through link_row field to text. Returns
    ``(user, table, lookup_field)`` with the lookup field refreshed and errored.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user, name="table")
    table_2 = data_fixture.create_database_table(
        user=user, database=table.database, name="table 2"
    )
    data_fixture.create_text_field(name="p", table=table, primary=True)
    data_fixture.create_text_field(name="primaryfield", table=table_2, primary=True)
    looked_up_field = data_fixture.create_text_field(name="lookupfield", table=table_2)

    link_row_field = FieldHandler().create_field(
        user, table, "link_row", name="linkrowfield", link_row_table=table_2
    )

    table_2_model = table_2.get_model(attribute_names=True)
    a = table_2_model.objects.create(
        lookupfield="option a", primaryfield="primary a", order=0
    )
    b = table_2_model.objects.create(
        lookupfield="option b", primaryfield="primary b", order=1
    )

    table_model = table.get_model(attribute_names=True)
    table_row = table_model.objects.create()
    table_row.linkrowfield.add(a.id)
    table_row.linkrowfield.add(b.id)
    table_row.save()

    lookup_field = FieldHandler().create_field(
        user,
        table,
        "lookup",
        name="lookup_field",
        through_field_id=link_row_field.id,
        target_field_id=looked_up_field.id,
    )
    lookup_field.refresh_from_db()
    assert lookup_field.formula_type == "array"

    # Break the lookup by converting its through link_row field to text so the lookup
    # can no longer traverse the relationship and becomes invalid.
    FieldHandler().update_field(user, link_row_field, new_type_name="text")

    lookup_field.refresh_from_db()
    assert lookup_field.formula_type == "invalid"

    return user, table, lookup_field


@pytest.mark.django_db
def test_link_row_field_converter_applicable(data_fixture):
    table = data_fixture.create_database_table()
    table_2 = data_fixture.create_database_table(database=table.database)
    table_3 = data_fixture.create_database_table(database=table.database)
    text_field = data_fixture.create_text_field(table=table)
    link_row_field_1 = LinkRowField.objects.create(
        table=table, link_row_table=table_2, order=1
    )
    link_row_field_2 = LinkRowField.objects.create(
        table=table, link_row_table=table_3, order=2
    )
    link_row_field_3 = LinkRowField.objects.create(
        table=table, link_row_table=table_2, order=3
    )

    converter = LinkRowFieldConverter()
    assert converter.is_applicable(None, text_field, link_row_field_1)
    assert converter.is_applicable(None, link_row_field_1, text_field)
    assert converter.is_applicable(None, link_row_field_1, link_row_field_2)
    assert converter.is_applicable(None, link_row_field_2, link_row_field_1)
    assert not converter.is_applicable(None, link_row_field_1, link_row_field_3)


@pytest.mark.django_db
def test_convert_invalid_jsonb_formula_field_to_multiple_select(data_fixture):
    """
    An array/lookup formula field is backed by a physical ``jsonb`` column. When the
    formula becomes invalid it declares db type ``text`` while its column would
    otherwise stay ``jsonb`` — the divergence behind the Sentry
    ``regexp_split_to_array(jsonb, unknown) does not exist`` crash.

    With the recreate-gate fix (``should_recreate_when_old_type_was`` returning
    ``db_column_is_jsonb``), invalidation recreates the column to ``text`` during the
    link_row -> text update, so by the time this converter runs the source column is
    already ``text``. This test therefore asserts the forward-looking gate keeps the
    conversion healthy; it does NOT exercise a residual ``jsonb`` column (see
    ``test_convert_diverged_jsonb_text_column_to_multiple_select`` for that path).
    """

    user, table, lookup_field = _create_invalid_jsonb_lookup_field(data_fixture)

    # Must not raise ProgrammingError: regexp_split_to_array(jsonb, unknown).
    FieldHandler().update_field(user, lookup_field, new_type_name="multiple_select")

    lookup_field.refresh_from_db()
    assert field_type_registry.get_by_model(lookup_field).type == "multiple_select"


@pytest.mark.django_db
def test_convert_diverged_jsonb_text_column_to_multiple_select(data_fixture):
    """
    Regression for the reported production state: a field already diverged
    (declared ``text`` / physical ``jsonb``) before the recreate-gate fix shipped.

    The gate fix cannot heal such pre-existing columns, so this test forces the
    column back to ``jsonb`` after invalidation to simulate a field that invalidated
    on an old version. The multiple_select converter must still heal it at conversion
    time via ``force_alter_column=True`` (an unconditional ``USING ::text`` rewrite)
    instead of feeding a ``jsonb`` column to ``regexp_split_to_array``.

    This test fails with ``ProgrammingError`` if ``force_alter_column=True`` is
    reverted in ``TextFieldToMultipleSelectFieldConverter``.
    """

    user, table, lookup_field = _create_invalid_jsonb_lookup_field(data_fixture)

    # Simulate a column that diverged before the gate fix existed: physically retype
    # it back to jsonb while the field keeps declaring text.
    table_name = table.get_database_table_name()
    db_column = lookup_field.db_column
    with connection.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {table_name} "
            f'ALTER COLUMN "{db_column}" TYPE jsonb '
            f"USING to_jsonb(coalesce(\"{db_column}\"::text, ''))"
        )

    # Must not raise ProgrammingError: regexp_split_to_array(jsonb, unknown).
    FieldHandler().update_field(user, lookup_field, new_type_name="multiple_select")

    lookup_field.refresh_from_db()
    assert field_type_registry.get_by_model(lookup_field).type == "multiple_select"
