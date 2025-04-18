import ZaraMonitor
import json
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
discord_logger = logging.getLogger('Discord')
monitor_logger = logging.getLogger('Monitor Task')

class MonitorTask:
    def __init__(self, bot, channel_id, monitor, item_name, role, img_link):
        self.bot = bot
        self.channel_id = channel_id
        self.monitor = monitor
        self.task = asyncio.create_task(self.run())
        self.item_name = item_name
        self.role = role
        self.img_link = img_link


    async def run(self):
        try:
            while True:
                in_stock = await self.monitor.check_stock()
                size_mapping = await self.monitor.get_sku_size_mapping()
                print(size_mapping)

                if self.monitor.has_stock_changed():
                    channel = self.bot.get_channel(self.channel_id)
                    if channel and in_stock:
                        stock_info = ""
                        for sku, status in self.monitor.current_stock.items():
                            if status in ["in_stock", "low_on_stock"]:
                                size = size_mapping.get(sku)
                                if size != "Unknown":
                                    stock_info += f"    {size}\n"

                        if not stock_info:
                            stock_info = "    Sizing Info Unavailable"

                        embed = discord.Embed(
                            title=self.item_name,
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Product", value=self.monitor.URL, inline=False)
                        embed.add_field(name="Status", value="In Stock" if in_stock else "Out of Stock", inline=False)
                        embed.add_field(name="Current Stock", value=stock_info, inline=False)
                        embed.set_image(url=self.img_link)

                        await channel.send(f'{self.role.mention}')
                        await channel.send(embed=embed)

                        await asyncio.sleep(20)

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            monitor_logger.info(f"Monitor for {self.monitor.URL} cancelled.")
        except Exception as e:
            monitor_logger.error(f"Error in monitor task: {e}")


class ZaraBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitors = {}
        self.monitor_tasks = {}
        try:
            with open("config.json", "r") as f:
                self.config = json.load(f)
        except Exception as e:
            discord_logger.error(f"Failed to load config: {e}")
            raise

    async def setup_hook(self):
        try:
            await self.tree.sync()
            discord_logger.info("Successfully synced commands")
        except Exception as e:
            discord_logger.error(f"Failed to sync commands: {e}")
            raise

    async def on_ready(self):
        discord_logger.info(f'Logged on as {self.user}!')
        discord_logger.info('------')


intents = discord.Intents.default()
intents.message_content = True
bot = ZaraBot(command_prefix='!', intents=intents)

def get_item_name(url):
    options = Options()
    options.add_argument('--headless') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--remote-debugging-port=9222')

    service = Service('/usr/local/bin/chromedriver')

    driver = webdriver.Chrome(service=service, options=options) 
    driver.get(url)

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    product_name = soup.find("h1", class_="product-detail-info__header-name")

    driver.quit()

    return product_name.text.strip()


@bot.tree.command(name="monitor", description="Start monitoring a Zara product")
@app_commands.describe(url="The Zara product URL to monitor")
async def monitor(interaction: discord.Interaction, url: str, role: discord.Role, img_link: str):
    if interaction.channel_id not in bot.monitors:
        bot.monitors[interaction.channel_id] = []
        bot.monitor_tasks[interaction.channel_id] = []

    for existing_monitor in bot.monitors[interaction.channel_id]:
        if existing_monitor.URL == url:
            await interaction.response.send_message(f"This product is already being monitored: {url}")
            return

    try:
        item_name = get_item_name(url)

        monitor = ZaraMonitor.ZaraMonitor(url, item_name)
        await monitor.initialize()
        bot.monitors[interaction.channel_id].append(monitor)

        monitor_task = MonitorTask(bot, interaction.channel_id, monitor, item_name, role, img_link)
        bot.monitor_tasks[interaction.channel_id].append(monitor_task)

        await interaction.response.send_message(f"Started monitoring product: {url}")
    except Exception as e:
        await interaction.response.send_message(f"Error starting monitor: {str(e)}")


@bot.tree.command(name="stop", description="Stop monitoring a product or list monitored products")
@app_commands.describe(index="The number of the product to stop monitoring (optional)")
async def stop(interaction: discord.Interaction, index: int = None):
    if interaction.channel_id not in bot.monitors or not bot.monitors[interaction.channel_id]:
        await interaction.response.send_message("No products are being monitored in this channel")
        return

    if index is None:
        embed = discord.Embed(title="Monitored Products", color=discord.Color.blue())
        for i, monitor in enumerate(bot.monitors[interaction.channel_id], 1):
            embed.add_field(name=f"Product {i}", value=monitor.URL, inline=False)
        embed.add_field(name="To stop monitoring", value="Use /stop <number> to stop monitoring a specific product", inline=False)
        await interaction.response.send_message(embed=embed)
        return

    try:
        if 1 <= index <= len(bot.monitors[interaction.channel_id]):
            removed_monitor = bot.monitors[interaction.channel_id].pop(index - 1)
            removed_task = bot.monitor_tasks[interaction.channel_id].pop(index - 1)
            removed_task.task.cancel()

            await interaction.response.send_message(f"Stopped monitoring product: {removed_monitor.URL}")

            if not bot.monitors[interaction.channel_id]:
                del bot.monitors[interaction.channel_id]
                del bot.monitor_tasks[interaction.channel_id]
        else:
            await interaction.response.send_message("Invalid product number. Use /stop to see available products.")
    except Exception as e:
        await interaction.response.send_message(f"Error stopping monitor: {str(e)}")


@bot.tree.command(name="status", description="Check the current monitoring status of all products")
async def status(interaction: discord.Interaction):
    if interaction.channel_id not in bot.monitors or not bot.monitors[interaction.channel_id]:
        await interaction.response.send_message("No products are being monitored in this channel")
        return

    embed = discord.Embed(title="Zara Stock Update", color=discord.Color.green())
    for i, monitor in enumerate(bot.monitors[interaction.channel_id], 1):
        in_stock = await monitor.check_stock()
        size_mapping = await monitor.get_sku_size_mapping()

        monitor_logger.info(f"Size mapping received: {size_mapping}")
        monitor_logger.info(f"Current stock: {monitor.current_stock}")

        stock_info = ""
        for sku, status in monitor.current_stock.items():
            if status in ["in_stock", "low_on_stock"]:
                size = size_mapping.get(sku, "Unknown")
                if size != "Unknown":
                    stock_info += f"    {size}\n"

        if not stock_info:
            stock_info = "    No sizes available"

        embed.add_field(name="Product", value=monitor.URL, inline=False)
        embed.add_field(name="Status", value="In Stock" if in_stock else "Out of Stock", inline=False)
        embed.add_field(name="Current Stock", value=stock_info, inline=False)

        if in_stock:
            await interaction.channel.send("<@&1360676493960806490>")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="clear", description="Clear the channel history")
async def clear(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    channel = interaction.channel
    try:
        await channel.purge(limit=None)
        await interaction.followup.send("Cleared all the channel's messages", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to delete messages in this channel", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred while clearing messages: {str(e)}", ephemeral=True)


try:
    bot.run(bot.config['discord_token'])
except Exception as e:
    discord_logger.error(f"Failed to start bot: {e}")
    raise
