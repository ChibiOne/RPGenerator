import click
import redis.asyncio as redis
import asyncio
import json
import pickle
from pathlib import Path
from datetime import datetime
import logging
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich import print as rprint
from rich.prompt import Prompt, Confirm
import shutil
import csv
import yaml
from dataclasses import asdict
import time

from ..config.settings import REDIS_CONFIG
# utils/redis_manager.py

console = Console()

class RedisDatabaseManager:
    def __init__(self):
        self.redis_url = 'redis://localhost'
        self.player_db = 0
        self.game_db = 1
        self.backup_dir = Path('backups')
        self.data_dir = Path('data')
        self.export_dir = Path('exports')
        self.player_redis = None
        self.game_redis = None

    async def connect(self):
        """Connect to Redis databases"""
        self.player_redis = await redis.from_url(self.redis_url, db=self.player_db)
        self.game_redis = await redis.from_url(self.redis_url, db=self.game_db)

    async def cleanup(self):
        """Close Redis connections"""
        if self.player_redis:
            await self.player_redis.aclose()
        if self.game_redis:
            await self.game_redis.aclose()

    async def search_database(self, query: str, search_type: str = 'all'):
        """Search through database contents"""
        results = {'areas': [], 'items': [], 'players': []}
        query = query.lower()

        if search_type in ['all', 'areas']:
            areas = await self.list_areas()
            results['areas'] = [
                area for area in areas.items()
                if query in area[0].lower() or
                query in str(area[1].get('description', '')).lower()
            ]

        if search_type in ['all', 'items']:
            items = await self.list_items()
            results['items'] = [
                item for item in items.items()
                if query in item[0].lower() or
                query in str(item[1].get('description', '')).lower()
            ]

        if search_type in ['all', 'players']:
            players = await self.list_players()
            results['players'] = [
                player for player in players.items()
                if query in str(player).lower()
            ]

        return results

    async def get_performance_stats(self):
        """Get detailed performance statistics"""
        start_time = time.time()
        
        stats = {
            'memory': await self.game_redis.info('memory'),
            'cpu': await self.game_redis.info('cpu'),
            'stats': await self.game_redis.info('stats'),
            'query_times': {}
        }

        # Measure query times
        times = {}
        
        start = time.time()
        await self.game_redis.hlen('areas')
        times['areas_query'] = time.time() - start

        start = time.time()
        await self.game_redis.hlen('items')
        times['items_query'] = time.time() - start

        start = time.time()
        await self.player_redis.keys('*')
        times['players_query'] = time.time() - start

        stats['query_times'] = times
        stats['total_time'] = time.time() - start_time

        return stats

    async def validate_data(self):
        """Validate database contents"""
        issues = []

        # Validate areas
        areas = await self.list_areas()
        for name, area in areas.items():
            if not name:
                issues.append(f"Area with empty name found")
            if not area.get('description'):
                issues.append(f"Area '{name}' missing description")
            if 'danger_level' not in area:
                issues.append(f"Area '{name}' missing danger level")

        # Validate items
        items = await self.list_items()
        for name, item in items.items():
            if not name:
                issues.append(f"Item with empty name found")
            if not item.get('description'):
                issues.append(f"Item '{name}' missing description")
            if 'value' not in item:
                issues.append(f"Item '{name}' missing value")

        # Validate players
        players = await self.list_players()
        for user_id, player in players.items():
            if not user_id:
                issues.append(f"Player with empty ID found")
            if not player.get('name'):
                issues.append(f"Player '{user_id}' missing name")

        return issues

    async def export_data(self, format_type: str, output_path: Path):
        """Export data to various formats"""
        data = {
            'areas': await self.list_areas(),
            'items': await self.list_items(),
            'players': await self.list_players()
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_type == 'json':
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)
        
        elif format_type == 'yaml':
            with open(output_path, 'w') as f:
                yaml.dump(data, f)
        
        elif format_type == 'csv':
            # Export each type to a separate CSV file
            for data_type, items in data.items():
                csv_path = output_path.parent / f"{data_type}.csv"
                with open(csv_path, 'w', newline='') as f:
                    if items:
                        writer = csv.DictWriter(f, fieldnames=items[next(iter(items))].keys())
                        writer.writeheader()
                        for name, item in items.items():
                            row = {'name': name, **item}
                            writer.writerow(row)

    async def list_players(self):
        """Get list of all players"""
        player_keys = await self.player_redis.keys('*')
        players = {}
        for key in player_keys:
            data = await self.player_redis.get(key)
            players[key] = pickle.loads(data)
        return players

    async def get_player_details(self, player_id: str):
        """Get detailed information about a specific player"""
        data = await self.player_redis.get(player_id)
        if data:
            return pickle.loads(data)
        return None

# New CLI commands

@cli.command()
@click.argument('query')
@click.option('--type', '-t', type=click.Choice(['all', 'areas', 'items', 'players']), default='all')
def search(query, type):
    """Search through database contents"""
    async def do_search():
        manager = RedisDatabaseManager()
        await manager.connect()
        
        try:
            results = await manager.search_database(query, type)
            
            if results['areas']:
                table = Table(title="Matching Areas")
                table.add_column("Name", style="cyan")
                table.add_column("Description", style="green")
                for name, area in results['areas']:
                    table.add_row(name, area.get('description', ''))
                console.print(table)
                
            if results['items']:
                table = Table(title="Matching Items")
                table.add_column("Name", style="cyan")
                table.add_column("Description", style="green")
                for name, item in results['items']:
                    table.add_row(name, item.get('description', ''))
                console.print(table)
                
            if results['players']:
                table = Table(title="Matching Players")
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="green")
                for player_id, player in results['players']:
                    table.add_row(player_id, player.get('name', ''))
                console.print(table)
                
        finally:
            await manager.cleanup()
    
    asyncio.run(do_search())

@cli.command()
def performance():
    """Show detailed performance statistics"""
    async def show_performance():
        manager = RedisDatabaseManager()
        await manager.connect()
        
        try:
            stats = await manager.get_performance_stats()
            
            table = Table(title="Performance Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            # Memory stats
            table.add_row("Used Memory", f"{stats['memory']['used_memory_human']}")
            table.add_row("Peak Memory", f"{stats['memory']['used_memory_peak_human']}")
            
            # CPU stats
            table.add_row("CPU Sys", f"{stats['cpu']['used_cpu_sys']}")
            table.add_row("CPU User", f"{stats['cpu']['used_cpu_user']}")
            
            # Query times
            for query, time in stats['query_times'].items():
                table.add_row(f"{query.replace('_', ' ').title()}", f"{time*1000:.2f}ms")
            
            console.print(table)
            
        finally:
            await manager.cleanup()
    
    asyncio.run(show_performance())

@cli.command()
def validate():
    """Validate database contents"""
    async def do_validate():
        manager = RedisDatabaseManager()
        await manager.connect()
        
        try:
            issues = await manager.validate_data()
            
            if issues:
                table = Table(title="Validation Issues")
                table.add_column("Issue", style="red")
                
                for issue in issues:
                    table.add_row(issue)
                
                console.print(table)
            else:
                rprint("[green]No validation issues found![/green]")
            
        finally:
            await manager.cleanup()
    
    asyncio.run(do_validate())

@cli.command()
@click.argument('format_type', type=click.Choice(['json', 'yaml', 'csv']))
@click.argument('output_path', type=click.Path())
def export(format_type, output_path):
    """Export data to various formats"""
    async def do_export():
        manager = RedisDatabaseManager()
        await manager.connect()
        
        try:
            await manager.export_data(format_type, Path(output_path))
            rprint(f"[green]Data exported successfully to {output_path}![/green]")
        finally:
            await manager.cleanup()
    
    asyncio.run(do_export())

@cli.command()
@click.argument('player_id', required=False)
def players(player_id):
    """List players or show detailed player info"""
    async def show_players():
        manager = RedisDatabaseManager()
        await manager.connect()
        
        try:
            if player_id:
                player = await manager.get_player_details(player_id)
                if player:
                    table = Table(title=f"Player Details: {player_id}")
                    table.add_column("Attribute", style="cyan")
                    table.add_column("Value", style="green")
                    
                    for key, value in player.items():
                        table.add_row(str(key), str(value))
                    
                    console.print(table)
                else:
                    rprint(f"[red]Player {player_id} not found[/red]")
            else:
                players = await manager.list_players()
                
                table = Table(title="Players")
                table.add_column("ID", style="cyan")
                table.add_column("Name", style="green")
                table.add_column("Level", style="yellow")
                
                for player_id, player in players.items():
                    table.add_row(
                        str(player_id),
                        str(player.get('name', 'N/A')),
                        str(player.get('level', 'N/A'))
                    )
                
                console.print(table)
            
        finally:
            await manager.cleanup()
    
    asyncio.run(show_players())

class ShardAwareRedisDB:
    def __init__(self, bot):
        self.bot = bot
        self.redis_pools: Dict[int, redis.Redis] = {}
        self.default_ttl = 3600
        self.lock = asyncio.Lock()

    async def init_pools(self):
        """Initialize Redis connection pools for each shard"""
        try:
            for shard_id in (self.bot.shards.keys() if self.bot.shard_count else [None]):
                pool = await redis.from_url(
                    REDIS_CONFIG['url'],
                    encoding='utf-8',
                    decode_responses=False,
                    max_connections=10
                )
                self.redis_pools[shard_id] = pool
                
            logging.info(f"Initialized Redis pools for {len(self.redis_pools)} shards")
        except Exception as e:
            logging.error(f"Failed to initialize Redis pools: {e}")
            raise

    def get_key(self, guild_id: Optional[int], key: str) -> str:
        """Generate Redis key with shard-specific prefix"""
        shard_id = (guild_id >> 22) % self.bot.shard_count if guild_id and self.bot.shard_count else 'global'
        return f"shard:{shard_id}:{key}"

    async def get_pool(self, guild_id: Optional[int] = None) -> redis.Redis:
        """Get Redis pool for the appropriate shard"""
        shard_id = (guild_id >> 22) % self.bot.shard_count if guild_id and self.bot.shard_count else None
        if shard_id not in self.redis_pools:
            # Initialize pool if it doesn't exist
            await self.init_pools()
        return self.redis_pools.get(shard_id, self.redis_pools[None])
if __name__ == '__main__':
    try:
        import rich
        import yaml
    except ImportError:
        console.print("[yellow]Installing required packages...[/yellow]")
        import subprocess
        subprocess.check_call(["pip", "install", "rich", "click", "pyyaml"])
        import rich
        import yaml
    
    cli()