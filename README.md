# Ban Royale / Ban War

## Usage

1. Install python (if you dont have it already) and dependencies in requirements.txt using
```python
pip install -r requirements.txt
``` 

2. Fill out the env with relevant details

3. Run
```python
python main.py
```

4. Have fun

## Commands

### Basic Commands
- `!enable` - Enable the bot royale functionality (Bot Master only)
- `!disable` - Disable the bot royale functionality (Bot Master only)
- `!ban <user>` or `!b <user>` - Attempt to ban a user with a configurable chance
- `!banchance <percentage>` or `!bc <percentage>` - Set the ban success chance (Bot Master only)
- `!bandelay <seconds>` or `!bd <seconds>` - Set delay between ban operations (0-60 seconds, Bot Master only)
- `!config` or `!cfg` - Display current bot configuration in an embed (Bot Master only)

### Unban Commands
- `!unbanall` or `!ua` - Unban all users who were banned during the event (Bot Master only)
  - **Rate Limited**: Includes automatic delays and retry logic to prevent Discord rate limiting
  - **Progress Updates**: Shows real-time progress during mass unban operations

**Note**: The `!unbanall` command only works for users who were banned during the current Bot Royale event in the current server. Users banned through other means cannot be unbanned using this command. The bot automatically tracks which users were banned during the event for each server separately in a file called `event_banned_users.json`. This prevents cross-server interference - unbanning users in one server won't affect another server's banned users. Individual unbans should be handled through your moderation bot.

## Safety Features

- **Rate Limiting Protection**: All ban/unban operations include automatic retry logic with progressive backoff to handle Discord API rate limits
- **Configurable Ban Delays**: Set custom delays between ban operations (default 2 seconds) to prevent spam and rate limits
- **Server Isolation**: Each server maintains separate banned user lists to prevent cross-server interference
- **Progress Tracking**: Mass unban operations show real-time progress and completion status
- **Error Handling**: Graceful handling of permissions errors, rate limits, and network issues
- **Automatic Retries**: Failed operations due to rate limits are automatically retried up to 3 times with exponential backoff

## Configuration

You can configure the bot behavior using environment variables in your `.env` file:

- `BAN_CHANCE` - Default ban success rate (0.0-1.0, default: 0.99)
- `BAN_DELAY` - Default delay between ban operations in seconds (default: 2.0)
- `BOT_MASTER_ROLE` - Role ID that can control the bot
- `BAN_LOGS_CHANNEL` - Channel ID for ban/unban logs
- `BAN_CHANNEL` - Channel ID where ban commands are allowed
- `REACT_EMOJI` - Emoji to react with on successful bans