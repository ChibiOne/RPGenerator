import click
import asyncio
from setup_redis import RedisDatabaseSetup

@click.group()
def cli():
    """Redis Database Management CLI"""
    pass

@cli.command()
def setup():
    """Initial database setup"""
    asyncio.run(setup_databases())

@cli.command()
def clear():
    """Clear all databases"""
    if click.confirm('This will delete all data. Are you sure?'):
        setup = RedisDatabaseSetup()
        asyncio.run(setup.clear_databases())

@cli.command()
def verify():
    """Verify database setup"""
    setup = RedisDatabaseSetup()
    asyncio.run(setup.verify_setup())

if __name__ == '__main__':
    cli()