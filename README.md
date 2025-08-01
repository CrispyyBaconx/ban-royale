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
- `!endgame` or `!eg` - End the current game, disable bot, unban all participants, and reset state (Bot Master only)

### Decay Mode Commands
- `!decay` or `!d` - Toggle decay mode on/off (Bot Master only)
- `!decaymin <percentage>` or `!dmin <percentage>` - Set minimum decay chance (Bot Master only)
- `!decaymax <percentage>` or `!dmax <percentage>` - Set maximum decay chance (Bot Master only)

### Unban Commands
- `!unbanall` or `!ua` - Unban all users who were banned during the event (Bot Master only)
  - **Rate Limited**: Includes automatic delays and retry logic to prevent Discord rate limiting
  - **Progress Updates**: Shows real-time progress during mass unban operations

**Note**: The `!unbanall` command only works for users who were banned during the current Bot Royale event in the current server. Users banned through other means cannot be unbanned using this command. The bot automatically tracks which users were banned during the event for each server separately in a file called `event_banned_users.json`. This prevents cross-server interference - unbanning users in one server won't affect another server's banned users. Individual unbans should be handled through your moderation bot.

## Decay Mode

Decay mode implements an **inverse curve** for ban chance based on how many people have been banned during the event. This creates a dynamic experience where:

- **High ban chance** when the event starts (many participants)
- **Decreasing ban chance** as more people get banned (fewer remaining participants)
- **Configurable min/max** chances to ensure the game remains fair and fun

### How Decay Works

1. **Enable decay mode**: Use `!decay` to toggle decay mode on/off
2. **Configure range**: Set min/max chances with `!decaymin` and `!decaymax`
3. **Automatic calculation**: Member count is automatically calculated (excluding bots and bot masters)
4. **Dynamic adjustment**: Ban chance automatically adjusts based on `(remaining_participants / effective_participants)`

### Example Decay Scenario
- Effective members: 100 (auto-calculated, excluding bots/masters)
- Min decay chance: 10%
- Max decay chance: 95%
- Current banned: 50
- **Current ban chance**: ~52.5% (halfway between min and max)

### Checkpoint Logging

When decay mode is enabled, the bot automatically logs progress milestones to the ban logs channel:

- **Automatic logging** at 10%, 20%, 30%, 40%, 50%, 60%, 70%, 80%, 90%, and 95% progress
- **Shows current ban chance** at each milestone
- **Progress tracking** with exact numbers (e.g., "25/100 banned")
- **One-time logging** - each checkpoint is only logged once per event
- **Server-specific** - checkpoints are tracked separately for each server
- **Auto-reset** - checkpoints automatically reset when the game ends

#### Example Checkpoint Log
```
📊 Decay Checkpoint 50% reached!
Progress: 50/100 banned (50.0%)
Current ban chance: 52.5%
```

### Game End Conditions

The game automatically ends and resets when:

1. **Win Condition**: Only 1 participant remains (excluding bots and bot masters) - *Automatic*
2. **Total Elimination**: All participants have been banned - *Automatic*
3. **Manual End**: Admin uses `!endgame` command - *Manual shutdown*

#### Automatic Game End (Win Conditions)
When win conditions are met:
- **Disables Ban Royale** - stops all ban commands from working
- **Preserves game state** - winners/losers remain as they are, no unbanning
- **Automatic announcement** in the ban logs channel
- **Requires manual cleanup** - admins can use `!endgame` to unban all and reset for next event

#### Manual Game End (`!endgame` command)
When an admin manually ends the game (works even after automatic win condition):
- **Unbans all participants** - automatically unbans everyone who was banned during the event
- **Resets decay mode** - turns off decay mode if it was enabled
- **Clears game state** - removes all tracking data and checkpoints
- **Complete cleanup** - full reset ready for the next event

#### Example Logs

**Automatic Win Condition:**
```
🏆 GAME OVER - We have a winner! 🏆
Only 1 participant remains out of 100 original members!
Ban Royale has been disabled. Use !endgame to unban all participants and reset for the next event.
```

**Manual Game End (Fresh Game):**
```
🏁 Ending game and shutting down Ban Royale...
Final stats: 45/100 participants were banned, 55 remain.

✅ Game cleanup completed!
• Ban Royale has been disabled
• Decay mode has been reset  
• Unbanned 45 users (Failed: 0)
• Game state has been cleared
```

**Manual Game End (After Win Condition):**
```
🏁 Cleaning up completed game...
Final stats: 99/100 participants were banned, 1 remain.

✅ Game cleanup completed!
• Decay mode has been reset  
• Unbanned 99 users (Failed: 0)
• Game state has been cleared
```

## Safety Features

- **Rate Limiting Protection**: All ban/unban operations include automatic retry logic with progressive backoff to handle Discord API rate limits
- **Configurable Ban Delays**: Set custom delays between ban operations (default 2 seconds) to prevent spam and rate limits
- **Server Isolation**: Each server maintains separate banned user lists to prevent cross-server interference
- **Progress Tracking**: Mass unban operations show real-time progress and completion status
- **Error Handling**: Graceful handling of permissions errors, rate limits, and network issues
- **Automatic Retries**: Failed operations due to rate limits are automatically retried up to 3 times with exponential backoff
- **Smart Member Counting**: Automatically excludes bots and bot masters from decay calculations
- **Comprehensive Game Management**: Win condition detection for all game modes and complete shutdown functionality with `!endgame`
- **Complete Reset Capability**: Manual game end includes bot disable, mass unban, decay reset, and state clearing

## Configuration

You can configure the bot behavior using environment variables in your `.env` file:

### Basic Settings
- `BAN_CHANCE` - Default ban success rate (0.0-1.0, default: 0.99)
- `BAN_DELAY` - Default delay between ban operations in seconds (default: 2.0)
- `BOT_MASTER_ROLE` - Role ID that can control the bot
- `BAN_LOGS_CHANNEL` - Channel ID for ban/unban logs
- `BAN_CHANNEL` - Channel ID where ban commands are allowed
- `REACT_EMOJI` - Emoji to react with on successful bans

### Decay Mode Settings
- `DECAY_MODE` - Enable decay mode by default (true/false, default: false)
- `MIN_DECAY_CHANCE` - Minimum ban chance in decay mode (0.0-1.0, default: 0.01)
- `MAX_DECAY_CHANCE` - Maximum ban chance in decay mode (0.0-1.0, default: 0.99)