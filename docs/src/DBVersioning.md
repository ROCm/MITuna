DB Schema versioning and migration
==================================


MITuna uses [Alembic](https://alembic.sqlalchemy.org/en/latest/index.html) for database schema versioning and migration. This tool is intended to work with SQLAlchemy.
Follow the instructions bellow to start versioning your DB and for sample on how to do a first schema migration.

MITuna's **requirements.txt** file contains the required library to install: alembic.

.. code-block::  
 :caption: You will need the following environment variables:

 export TUNA_DB_NAME=<db_name>
 export TUNA_DB_USER_NAME=<db_user>
 export TUNA_DB_USER_PASSWORD=<db_pwd>
 export TUNA_DB_HOSTNAME=<db_hostname>

These are used in `alembic/env.py` to set up the DB connection.

DB version upgrades/downgrades are located in alembic/versions. The alembic tool and it's '.ini' file are set up to work with the MITuna DB.

To start a migration file follow the steps bellow:

  1. $ alembic revision -m "create account table"
  2. Modify the new versioning file in MITuna/alembic/versions/ with the desired DB changes.
  3. Run the new migraton file: $ alembic upgrade head

For more details on how to modify the new versining file, or how to execute more complex migrations, follow along the [alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html#creating-an-environment)



