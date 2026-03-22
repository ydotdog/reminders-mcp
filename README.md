# reminders-mcp

An MCP (Model Context Protocol) server that connects Claude Code to Apple Reminders. Manage your reminders with natural language — tasks sync to your iPhone automatically via iCloud.

## Features

- **Add reminders** with title, notes, due date, priority, and list assignment
- **Batch add** multiple reminders at once
- **View reminders** — today's tasks, upcoming tasks, or by list
- **Complete reminders** by name (fuzzy match)
- **Search** across all lists
- **iCloud sync** — changes made on Mac appear on iPhone instantly

## Requirements

- macOS (uses AppleScript and JXA for Reminders access)
- Python 3.10+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

## Installation

### 1. Clone and set up

```bash
git clone https://github.com/anthropics/reminders-mcp.git  # replace with your repo
cd reminders-mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Register in Claude Code

Add to `~/.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "reminders": {
      "command": "/path/to/reminders-mcp/venv/bin/python",
      "args": ["/path/to/reminders-mcp/server.py"]
    }
  }
}
```

### 3. Restart Claude Code

The MCP server loads on startup. After restarting, you can use natural language to manage reminders.

## Available Tools

### Write

| Tool | Description | Parameters |
|------|-------------|------------|
| `reminders_add` | Add a single reminder | `title`, `notes?`, `due_date?`, `list_name?`, `priority?` |
| `reminders_add_multiple` | Batch add reminders | `tasks` (JSON array) |
| `reminders_complete` | Mark reminder as done | `title`, `list_name?` |

### Read

| Tool | Description | Parameters |
|------|-------------|------------|
| `reminders_today` | Get today's reminders | — |
| `reminders_upcoming` | Get upcoming reminders | `days?` (default 7) |
| `reminders_all` | Get all reminders in a list | `list_name?`, `include_completed?` |
| `reminders_search` | Search by keyword | `keyword` |
| `reminders_show_lists` | Show all lists with counts | — |

### Parameter Details

- **`due_date`**: `"YYYY-MM-DD HH:MM"` or `"YYYY-MM-DD"` (defaults to 09:00 if no time given)
- **`priority`**: `"high"`, `"medium"`, `"low"`, or `"none"` (default)
- **`list_name`**: Name of the Reminders list (default: `"Reminders"`)
- **`tasks`** (for batch): JSON array, e.g. `[{"title":"Buy milk","due_date":"2026-03-24"},{"title":"Call dentist"}]`

## Usage Examples

Once registered in Claude Code, just use natural language:

```
You: "Add a reminder: meeting tomorrow at 5pm"
Claude: → reminders_add(title="Meeting", due_date="2026-03-24 17:00")
      ✓ Added "Meeting" to list "Reminders", due: 2026-03-24 17:00

You: "What's on my list today?"
Claude: → reminders_today()
      [09:00] Write report
      [14:00] Team standup
      [17:00] Meeting

You: "Add three tasks: buy groceries, pick up package, pay water bill"
Claude: → reminders_add_multiple(tasks='[{"title":"Buy groceries"},...]')
      ✓ Added 3 reminders to "Reminders"

You: "Mark 'buy groceries' as done"
Claude: → reminders_complete(title="buy groceries")
      ✓ Completed "buy groceries"

You: "What do I have coming up this week?"
Claude: → reminders_upcoming(days=7)
      [2026-03-24 17:00] Meeting
      [2026-03-25 09:00] Dentist appointment
      [2026-03-27 10:00] Project deadline
```

## Architecture

- **Read operations** use JXA (JavaScript for Automation) for structured JSON-like output
- **Write operations** use AppleScript for reliable reminder creation/modification
- **Sync** is handled by macOS + iCloud automatically

## License

MIT
