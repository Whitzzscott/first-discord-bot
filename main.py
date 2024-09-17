import discord
from flask import Flask
from discord.ext import commands, tasks
from threading import Thread
import google.generativeai as genai
import os
import logging
import asyncio
from itertools import cycle

flask_app = Flask('')

@flask_app.route('/')
def health_check():
    return "I'm alive"

def start_flask():
    flask_app.run(host="0.0.0.0", port=8080)

def keep_flask_alive():
    thread = Thread(target=start_flask)
    thread.start()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
API_KEYS = [os.getenv('API_KEY1'), os.getenv('API_KEY2'), os.getenv('API_KEY3'), os.getenv('API_KEY4'), os.getenv('API_KEY5')]

api_key_cycle = cycle(API_KEYS)
current_api_key = next(api_key_cycle)
genai.configure(api_key=current_api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix='/', intents=intents)

active_sessions = {}
private_sessions = {}
system_prompt = "You are a helpful assistant. Respond to user queries with relevant information and a friendly tone."

custom_settings = {
    "context_limit": 2048,
    "top_k": 50,
    "temp": 1.0,
    "random_word": False,
    "min_word": False
}

personas = {
    "formal": "You are a formal and professional assistant. Use proper language and maintain a formal tone.",
    "informal": "You are an informal and casual assistant. Use conversational language and a casual tone.",
    "ai": "You are an AI assistant. Provide responses in a straightforward, neutral tone.",
    "human": "You are a human-like assistant. Provide responses with empathy and a conversational tone.",
    "rp": "You are a role-playing assistant. Respond in a creative, immersive manner suitable for role-playing scenarios.",
    "coding": "You are a technical coding assistant. Provide precise and technical explanations related to coding and programming."
}

admin_role_id = 1284807889696849983
test_channel_id = 1284809414070632508

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def configure_new_key():
    global current_api_key, model
    current_api_key = next(api_key_cycle)
    genai.configure(api_key=current_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

status_cycle = cycle(['with Python', 'JetHub'])

@tasks.loop(seconds=10)
async def update_status():
    await bot.change_presence(activity=discord.Game(next(status_cycle)))

@bot.event
async def on_ready():
    update_status.start()
    logging.info(f'Connected bot: {bot.user.name}#{bot.user.discriminator}')
    logging.info('Bot is online and ready to receive commands.')
    await bot.tree.sync()
    await test_commands()

@bot.tree.command(name="initiate", description="Start a chat session")
async def initiate(interaction: discord.Interaction):
    user_id = interaction.user.id
    active_sessions[user_id] = {"private": False, "message_count": 0}
    logging.info(f'{interaction.user} initiated a chat session.')
    await interaction.response.send_message("Chat initiated. Type your message and I will respond. Type /end to stop the chat.")
    try:
        await interaction.user.send("Chat initiated. Type your message and I will respond. Type /end to stop the chat.")
    except discord.Forbidden:
        pass

@bot.tree.command(name="end", description="End the current chat session")
async def end(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in active_sessions:
        del active_sessions[user_id]
        private_sessions.pop(user_id, None)
        logging.info(f'{interaction.user} ended the chat session.')
        await interaction.response.send_message("Chat ended.")
        try:
            await interaction.user.send("Chat ended.")
        except discord.Forbidden:
            pass
    else:
        await interaction.response.send_message("No active chat session to end.")

@bot.tree.command(name="clear_all", description="Clear all initiated chat sessions and messages")
async def clear_all(interaction: discord.Interaction):
    if any(role.id == admin_role_id for role in interaction.user.roles):
        global active_sessions
        active_sessions.clear()
        private_sessions.clear()
        logging.info(f'{interaction.user} cleared all initiated chat sessions and messages.')
        await interaction.response.send_message("All initiated chat sessions and messages have been cleared.")
        try:
            await interaction.user.send("All initiated chat sessions and messages have been cleared.")
        except discord.Forbidden:
            pass
    else:
        await interaction.response.send_message("You do not have permission to use this command.")

@bot.tree.command(name="change_prompt", description="Change the system prompt")
async def change_prompt(interaction: discord.Interaction, new_prompt: str):
    global system_prompt
    system_prompt = new_prompt
    logging.info(f'{interaction.user} changed the system prompt to: {new_prompt}')
    await interaction.response.send_message(f"System prompt updated to: {system_prompt}")
    try:
        await interaction.user.send(f"System prompt updated to: {system_prompt}")
    except discord.Forbidden:
        pass

@bot.tree.command(name="customize", description="List and change AI customization settings")
async def customize(interaction: discord.Interaction, setting: str = None, value: str = None):
    global custom_settings
    if setting and value:
        if setting in custom_settings:
            if setting in ["random_word", "min_word"]:
                custom_settings[setting] = value.lower() == "true"
            else:
                try:
                    custom_settings[setting] = float(value)
                    if setting in ["top_k", "context_limit"] and custom_settings[setting] <= 0:
                        await interaction.response.send_message(f"{setting} must be greater than 0.")
                        try:
                            await interaction.user.send(f"{setting} must be greater than 0.")
                        except discord.Forbidden:
                            pass
                        return
                except ValueError:
                    await interaction.response.send_message(f"Invalid value for {setting}.")
                    try:
                        await interaction.user.send(f"Invalid value for {setting}.")
                    except discord.Forbidden:
                        pass
                    return
            logging.info(f'{interaction.user} updated {setting} to {custom_settings[setting]}.')
            await interaction.response.send_message(f"{setting} updated to {custom_settings[setting]}.")
            try:
                await interaction.user.send(f"{setting} updated to {custom_settings[setting]}.")
            except discord.Forbidden:
                pass
        else:
            await interaction.response.send_message(f"Unknown setting: {setting}.")
            try:
                await interaction.user.send(f"Unknown setting: {setting}.")
            except discord.Forbidden:
                pass
    else:
        settings_list = "\n".join([f"{key}: {value}" for key, value in custom_settings.items()])
        logging.info(f'{interaction.user} requested AI customization settings.')
        await interaction.response.send_message(f"Current settings:\n{settings_list}")
        try:
            await interaction.user.send(f"Current settings:\n{settings_list}")
        except discord.Forbidden:
            pass

@bot.tree.command(name="persona", description="Change the AI persona")
async def persona(interaction: discord.Interaction, new_persona: str):
    global system_prompt
    if new_persona in personas:
        system_prompt = personas[new_persona]
        logging.info(f'{interaction.user} switched persona to: {new_persona}')
        await interaction.response.send_message(f"Persona switched to: {new_persona}")
        try:
            await interaction.user.send(f"Persona switched to: {new_persona}")
        except discord.Forbidden:
            pass
    else:
        await interaction.response.send_message("Unknown persona. Available personas are: formal, informal, ai, human, rp, coding.")
        try:
            await interaction.user.send("Unknown persona. Available personas are: formal, informal, ai, human, rp, coding.")
        except discord.Forbidden:
            pass

@bot.tree.command(name="private", description="Make the chat private")
async def private(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in active_sessions:
        active_sessions[user_id]["private"] = True
        logging.info(f'{interaction.user} set the chat to private.')
        try:
            await interaction.response.send_message("Chat is now private. Only you and the bot can see the messages.")
            await interaction.user.send("Chat is now private. Only you and the bot can see the messages.")
        except discord.Forbidden:
            await interaction.response.send_message("I can't DM you. Please ensure your DM settings allow messages from this server.")
    else:
        await interaction.response.send_message("No active chat session to set private.")

@bot.tree.command(name="exit_private", description="Exit private chat mode but keep the chat session")
async def exit_private(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in active_sessions:
        active_sessions[user_id]["private"] = False
        logging.info(f'{interaction.user} exited private chat mode.')
        try:
            await interaction.response.send_message("Private mode exited. The chat is now visible to everyone.")
            await interaction.user.send("Private mode exited. The chat is now visible to everyone.")
        except discord.Forbidden:
            await interaction.response.send_message("I can't DM you. Please ensure your DM settings allow messages from this server.")
    else:
        await interaction.response.send_message("No active chat session to exit private mode.")

@bot.tree.command(name="quotes", description="Generate a random motivational quote")
async def quotes(interaction: discord.Interaction):
    try:
        logging.info(f'{interaction.user} requested a motivational quote.')
        prompt = "Generate a random motivational quote."
        response = await get_gemini_response(prompt)
        await interaction.response.send_message(f"Here is a motivational quote:\n{response}")
        try:
            await interaction.user.send(f"Here is a motivational quote:\n{response}")
        except discord.Forbidden:
            pass
    except Exception as e:
        logging.error(f'Error generating quote: {str(e)}')
        await interaction.response.send_message(f'Error: {str(e)}')
        try:
            await interaction.user.send(f'Error: {str(e)}')
        except discord.Forbidden:
            pass

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    user_id = message.author.id
    if user_id in active_sessions:
        if active_sessions[user_id]["private"]:
            if message.channel.id not in private_sessions.get(user_id, []):
                private_sessions.setdefault(user_id, []).append(message.channel.id)
                logging.info(f'{message.author} started a private chat session in {message.channel.id}.')
            if message.channel.type == discord.ChannelType.private:
                async with message.channel.typing():
                    query = message.content
                    logging.info(f'Received message from {message.author}: {query}')
                    response = await get_gemini_response(query)
                    logging.info(f'Response sent to {message.author}: {response}')

                    for i in range(0, len(response), 2000):
                        chunk = response[i:i+2000]
                        try:
                            await message.channel.send(chunk)
                        except discord.HTTPException as e:
                            logging.error(f'Error sending message chunk: {str(e)}')
            else:
                await message.channel.send(f'{message.author.mention}, you have reached your messaging limit. Please wait 10 minutes before chatting again.')
                return
        else:
            if active_sessions[user_id]["message_count"] >= 20:
                await message.channel.send(f'{message.author.mention}, you have reached your messaging limit. Please wait 10 minutes before chatting again.')
                return

            async with message.channel.typing():
                query = message.content
                logging.info(f'Received message from {message.author}: {query}')
                response = await get_gemini_response(query)
                logging.info(f'Response sent to {message.author}: {response}')

                for i in range(0, len(response), 2000):
                    chunk = response[i:i+2000]
                    try:
                        await message.channel.send(chunk)
                    except discord.HTTPException as e:
                        logging.error(f'Error sending message chunk: {str(e)}')

            active_sessions[user_id]["message_count"] += 1
            if active_sessions[user_id]["message_count"] >= 20:
                await asyncio.sleep(600)
                active_sessions[user_id]["message_count"] = 0

    await bot.process_commands(message)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author == bot.user:
        return

    user_id = before.author.id
    if user_id in active_sessions:
        if active_sessions[user_id]["private"]:
            if after.channel.type == discord.ChannelType.private:
                async with after.channel.typing():
                    query = after.content
                    logging.info(f'User edited message: {before.content} -> {after.content}')
                    response = await get_gemini_response(query)
                    logging.info(f'Response to edited message sent to {before.author}: {response}')

                    for i in range(0, len(response), 2000):
                        chunk = response[i:i+2000]
                        try:
                            await after.channel.send(chunk)
                        except discord.HTTPException as e:
                            logging.error(f'Error sending message chunk: {str(e)}')

async def get_gemini_response(query):
    global model
    try:
        response = model.generate_content(
            f"{system_prompt}\n\n{query}",
            safety_settings=[]
        )
        return response.text
    except Exception as e:
        if "429" in str(e):
            logging.warning('Rate limit exceeded, switching API key.')
            configure_new_key()
            return await get_gemini_response(query)
        logging.error(f'Error generating response: {str(e)}')
        return f'Error: {str(e)}'

async def test_commands():
    test_channel = bot.get_channel(test_channel_id)
    if test_channel:
        await test_channel.send("Bot online and ready!")

keep_flask_alive()
bot.run(DISCORD_TOKEN)
