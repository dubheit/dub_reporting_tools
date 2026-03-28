import logging

_logger = logging.getLogger(__name__)

OLD_MODULE_NAME = 'db_reporting_carbone'
NEW_MODULE_NAME = 'dub_reporting_carbone'


def pre_init_hook(env):
    """Migrate db_reporting_carbone to dub_reporting_carbone.

    This hook runs BEFORE the module installation and handles the database
    migration when the old db_* module is already installed.

    NOTE: Odoo creates the new module record in ir_module_module BEFORE calling
    this hook, so we cannot rely on checking if the new module exists.
    Instead, we check for old module data in ir_model_data.
    """
    _logger.info(f'Running pre_init_hook: migrating {OLD_MODULE_NAME} to {NEW_MODULE_NAME}')
    cr = env.cr

    # Check if old module has data in ir_model_data (the real source of truth)
    cr.execute(
        "SELECT COUNT(*) FROM ir_model_data WHERE module = %s",
        (OLD_MODULE_NAME,)
    )
    old_data_count = cr.fetchone()[0]

    if old_data_count == 0:
        _logger.info(f'No data for {OLD_MODULE_NAME} in ir_model_data, fresh install')
        # Clean up old module record if exists (orphan record)
        cr.execute("DELETE FROM ir_module_module WHERE name = %s", (OLD_MODULE_NAME,))
        return

    _logger.info(f'Found {old_data_count} records for {OLD_MODULE_NAME} in ir_model_data')

    # Delete duplicate records: if a record with the same name already exists
    # for the new module, delete the old one to avoid constraint violations
    cr.execute("""
        DELETE FROM ir_model_data old
        WHERE old.module = %s
        AND EXISTS (
            SELECT 1 FROM ir_model_data new
            WHERE new.module = %s
            AND new.name = old.name
            AND new.model = old.model
        )
    """, (OLD_MODULE_NAME, NEW_MODULE_NAME))
    deleted_duplicates = cr.rowcount
    if deleted_duplicates:
        _logger.info(f'Deleted {deleted_duplicates} duplicate records from ir_model_data')

    # Migrate remaining ir_model_data references
    cr.execute(
        "UPDATE ir_model_data SET module = %s WHERE module = %s",
        (NEW_MODULE_NAME, OLD_MODULE_NAME)
    )
    _logger.info(f'Migrated ir_model_data: {cr.rowcount} records')

    # Update dependencies that reference this module
    cr.execute(
        "UPDATE ir_module_module_dependency SET name = %s WHERE name = %s",
        (NEW_MODULE_NAME, OLD_MODULE_NAME)
    )
    if cr.rowcount:
        _logger.info(f'Updated ir_module_module_dependency: {cr.rowcount} records')

    # Clean up old module record from ir_module_module
    cr.execute("DELETE FROM ir_module_module WHERE name = %s", (OLD_MODULE_NAME,))
    if cr.rowcount:
        _logger.info(f'Deleted old module record from ir_module_module')

    _logger.info(f'Migration {OLD_MODULE_NAME} -> {NEW_MODULE_NAME} completed')
