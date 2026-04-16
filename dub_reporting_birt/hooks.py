import logging

_logger = logging.getLogger(__name__)

OLD_MODULE_NAME = "db_reporting_birt"
NEW_MODULE_NAME = "dub_reporting_birt"


def pre_init_hook(env):
    """Migrate db_reporting_birt to dub_reporting_birt.

    This hook runs BEFORE the module installation and handles the database
    migration when the old db_* module is already installed.
    """
    _logger.info(
        "Running pre_init_hook: migrating %s to %s",
        OLD_MODULE_NAME, NEW_MODULE_NAME,
    )
    cr = env.cr
    cr.execute(
        "SELECT COUNT(*) FROM ir_model_data WHERE module = %s",
        (OLD_MODULE_NAME,),
    )
    count = cr.fetchone()[0]
    if not count:
        _logger.info("No data for %s in ir_model_data, fresh install", OLD_MODULE_NAME)
        cr.execute(
            "DELETE FROM ir_module_module WHERE name = %s",
            (OLD_MODULE_NAME,),
        )
        return

    _logger.info("Found %d records for %s in ir_model_data", count, OLD_MODULE_NAME)

    # Remove duplicates that already exist under the new module name
    cr.execute(
        """
        DELETE FROM ir_model_data old
        WHERE old.module = %s
        AND EXISTS (
            SELECT 1 FROM ir_model_data new
            WHERE new.module = %s
            AND new.name = old.name
            AND new.model = old.model
        )
    """,
        (OLD_MODULE_NAME, NEW_MODULE_NAME),
    )
    _logger.info("Deleted %d duplicate records from ir_model_data", cr.rowcount)

    # Rename remaining records
    cr.execute(
        "UPDATE ir_model_data SET module = %s WHERE module = %s",
        (NEW_MODULE_NAME, OLD_MODULE_NAME),
    )
    _logger.info("Migrated ir_model_data: %d records", cr.rowcount)

    # Update module dependencies
    cr.execute(
        "UPDATE ir_module_module_dependency SET name = %s WHERE name = %s",
        (NEW_MODULE_NAME, OLD_MODULE_NAME),
    )
    _logger.info("Updated ir_module_module_dependency: %d records", cr.rowcount)

    # Delete old module record
    cr.execute(
        "DELETE FROM ir_module_module WHERE name = %s",
        (OLD_MODULE_NAME,),
    )
    _logger.info("Deleted old module record from ir_module_module")
    _logger.info("Migration %s -> %s completed", OLD_MODULE_NAME, NEW_MODULE_NAME)
