"""
Apple 提醒事项 MCP Server
通过 AppleScript 完整读写 macOS 提醒事项，iCloud 自动同步到 iPhone
"""

import json
import re
import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Apple Reminders",
    instructions="""你是一个 Apple 提醒事项管理助手。
当用户想添加任务时，从自然语言中提取：标题、备注、截止日期、列表、优先级。
- 如果用户没指定列表，默认用 "Reminders"
- 日期格式传入 "YYYY-MM-DD HH:MM"，只有日期则用 "YYYY-MM-DD"
- 优先级：high/medium/low/none，默认 none
- 查看任务时，先用 reminders_today 或 reminders_all
- 标记完成用 reminders_complete""",
)


def _escape_applescript(text: str) -> str:
    """转义 AppleScript 双引号字符串中的特殊字符"""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _escape_jxa(text: str) -> str:
    """转义 JXA 单引号字符串中的特殊字符"""
    return text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _run_applescript(script: str) -> tuple[bool, str]:
    """运行 AppleScript，返回 (成功, 输出/错误)"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, result.stdout.strip()


def _run_jxa(script: str) -> tuple[bool, str]:
    """运行 JXA (JavaScript for Automation)，返回 (成功, 输出/错误)"""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, result.stdout.strip()


def _build_date_script(due_date: str) -> str:
    """构建 AppleScript 日期设置代码。

    先将 day 设为 1 避免月份溢出问题（如 3月31日设 month=2 → 溢出到3月）。
    """
    if not due_date:
        return ""

    if not re.match(r"^\d{4}-\d{2}-\d{2}(\s\d{2}:\d{2})?$", due_date.strip()):
        raise ValueError(f"日期格式错误，应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM，收到: {due_date}")

    parts = due_date.strip().split(" ")
    date_part = parts[0]
    time_part = parts[1] if len(parts) > 1 else ""

    year, month, day = date_part.split("-")

    lines = [
        "set dueD to current date",
        "set day of dueD to 1",
        f"set year of dueD to {year}",
        f"set month of dueD to {int(month)}",
        f"set day of dueD to {int(day)}",
    ]

    if time_part:
        h, m = time_part.split(":")
        lines.append(f"set hours of dueD to {int(h)}")
        lines.append(f"set minutes of dueD to {int(m)}")
        lines.append("set seconds of dueD to 0")
    else:
        lines.append("set hours of dueD to 9")
        lines.append("set minutes of dueD to 0")
        lines.append("set seconds of dueD to 0")

    return "\n".join(lines)


def _priority_to_int(priority: str) -> int:
    """优先级映射到 Apple Reminders 数值"""
    mapping = {"high": 1, "medium": 5, "low": 9, "none": 0}
    return mapping.get(priority.lower(), 0)


# ─── 写入工具 ───


@mcp.tool()
def reminders_add(
    title: str,
    notes: str = "",
    due_date: str = "",
    list_name: str = "Reminders",
    priority: str = "none",
) -> str:
    """添加一个提醒事项。

    Args:
        title: 任务标题
        notes: 备注信息
        due_date: 截止日期，格式 "YYYY-MM-DD HH:MM" 或 "YYYY-MM-DD"
        list_name: 列表名称，默认 "Reminders"
        priority: 优先级 high/medium/low/none
    """
    escaped_title = _escape_applescript(title)
    escaped_notes = _escape_applescript(notes)
    escaped_list = _escape_applescript(list_name)
    pri = _priority_to_int(priority)

    props = f'name:"{escaped_title}"'
    if notes:
        props += f', body:"{escaped_notes}"'
    if pri > 0:
        props += f", priority:{pri}"

    try:
        date_script = _build_date_script(due_date)
    except ValueError as e:
        return f"添加失败: {e}"

    if date_script:
        script = f"""
{date_script}
tell application "Reminders"
    tell list "{escaped_list}"
        make new reminder with properties {{{props}, due date:dueD}}
    end tell
end tell
"""
    else:
        script = f"""
tell application "Reminders"
    tell list "{escaped_list}"
        make new reminder with properties {{{props}}}
    end tell
end tell
"""

    ok, msg = _run_applescript(script)
    if not ok:
        return f"添加失败: {msg}"

    result = f"已添加「{title}」到列表「{list_name}」"
    if due_date:
        result += f"，截止: {due_date}"
    return result


@mcp.tool()
def reminders_add_multiple(tasks: str) -> str:
    """批量添加多个提醒事项。

    Args:
        tasks: JSON 数组，每项含 title，可选 notes/due_date/list_name/priority。
               例: [{"title":"买菜","due_date":"2026-03-24"},{"title":"开会","due_date":"2026-03-24 17:00"}]
    """
    try:
        items = json.loads(tasks)
    except json.JSONDecodeError as e:
        return f"JSON 解析错误: {e}"

    if not isinstance(items, list):
        return "错误: tasks 必须是 JSON 数组"

    results = []
    for item in items:
        if not isinstance(item, dict) or "title" not in item:
            results.append("跳过: 缺少 title")
            continue
        r = reminders_add(
            title=item["title"],
            notes=item.get("notes", ""),
            due_date=item.get("due_date", ""),
            list_name=item.get("list_name", "Reminders"),
            priority=item.get("priority", "none"),
        )
        results.append(r)

    return "\n".join(results)


@mcp.tool()
def reminders_complete(title: str, list_name: str = "") -> str:
    """标记提醒事项为已完成。

    Args:
        title: 要完成的任务标题（模糊匹配）
        list_name: 列表名称，为空则搜索所有列表
    """
    escaped_title = _escape_applescript(title)

    if list_name:
        escaped_list = _escape_applescript(list_name)
        script = f"""
tell application "Reminders"
    set found to false
    set matchedReminders to (reminders of list "{escaped_list}" whose name contains "{escaped_title}" and completed is false)
    repeat with r in matchedReminders
        set completed of r to true
        set found to true
    end repeat
    if found then
        return "done"
    else
        return "not_found"
    end if
end tell
"""
    else:
        script = f"""
tell application "Reminders"
    set found to false
    repeat with L in every list
        set matchedReminders to (reminders of L whose name contains "{escaped_title}" and completed is false)
        repeat with r in matchedReminders
            set completed of r to true
            set found to true
        end repeat
    end repeat
    if found then
        return "done"
    else
        return "not_found"
    end if
end tell
"""

    ok, msg = _run_applescript(script)
    if not ok:
        return f"操作失败: {msg}"
    if "not_found" in msg:
        return f"未找到包含「{title}」的未完成任务"
    return f"已完成「{title}」"


# ─── 读取工具 ───


@mcp.tool()
def reminders_today() -> str:
    """获取今天到期的提醒事项。"""
    script = """
(() => {
    const app = Application('Reminders');
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
    const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);
    const results = [];

    app.lists().forEach(list => {
        list.reminders.whose({completed: false})().forEach(r => {
            const dd = r.dueDate();
            if (dd && dd >= todayStart && dd <= todayEnd) {
                const time = dd.getHours().toString().padStart(2,'0') + ':' + dd.getMinutes().toString().padStart(2,'0');
                results.push({
                    name: r.name(),
                    time: time,
                    list: list.name(),
                    body: r.body() || '',
                    priority: r.priority()
                });
            }
        });
    });

    results.sort((a, b) => a.time.localeCompare(b.time));

    if (results.length === 0) return '今天没有到期的提醒事项';

    return results.map(r => {
        let line = `[${r.time}] ${r.name}`;
        if (r.list !== 'Reminders') line += ` (${r.list})`;
        if (r.body) line += ` — ${r.body}`;
        return line;
    }).join('\\n');
})()
"""
    ok, msg = _run_jxa(script)
    if not ok:
        return f"查询失败: {msg}"
    return msg


@mcp.tool()
def reminders_upcoming(days: int = 7) -> str:
    """获取未来几天内到期的提醒事项。

    Args:
        days: 未来天数，默认 7 天
    """
    script = f"""
(() => {{
    const app = Application('Reminders');
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
    const futureEnd = new Date(todayStart.getTime() + {days} * 86400000);
    const results = [];

    app.lists().forEach(list => {{
        list.reminders.whose({{completed: false}})().forEach(r => {{
            const dd = r.dueDate();
            if (dd && dd >= todayStart && dd <= futureEnd) {{
                const dateStr = dd.getFullYear() + '-' +
                    (dd.getMonth()+1).toString().padStart(2,'0') + '-' +
                    dd.getDate().toString().padStart(2,'0');
                const timeStr = dd.getHours().toString().padStart(2,'0') + ':' +
                    dd.getMinutes().toString().padStart(2,'0');
                results.push({{
                    name: r.name(),
                    date: dateStr,
                    time: timeStr,
                    list: list.name(),
                    body: r.body() || '',
                    priority: r.priority()
                }});
            }}
        }});
    }});

    results.sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));

    if (results.length === 0) return '未来 {days} 天没有到期的提醒事项';

    return results.map(r => {{
        let line = `[${{r.date}} ${{r.time}}] ${{r.name}}`;
        if (r.list !== 'Reminders') line += ` (${{r.list}})`;
        if (r.body) line += ` — ${{r.body}}`;
        return line;
    }}).join('\\n');
}})()
"""
    ok, msg = _run_jxa(script)
    if not ok:
        return f"查询失败: {msg}"
    return msg


@mcp.tool()
def reminders_all(list_name: str = "Reminders", include_completed: bool = False) -> str:
    """获取指定列表中的所有提醒事项。

    Args:
        list_name: 列表名称，默认 "Reminders"
        include_completed: 是否包含已完成的，默认 false
    """
    escaped_list = _escape_jxa(list_name)
    filter_line = "list.reminders.whose({completed: false})()" if not include_completed else "list.reminders()"

    script = f"""
(() => {{
    const app = Application('Reminders');
    const list = app.lists.byName('{escaped_list}');
    const reminders = {filter_line};
    const results = [];

    reminders.forEach(r => {{
        const dd = r.dueDate();
        let dateStr = '';
        if (dd) {{
            dateStr = dd.getFullYear() + '-' +
                (dd.getMonth()+1).toString().padStart(2,'0') + '-' +
                dd.getDate().toString().padStart(2,'0') + ' ' +
                dd.getHours().toString().padStart(2,'0') + ':' +
                dd.getMinutes().toString().padStart(2,'0');
        }}
        results.push({{
            name: r.name(),
            date: dateStr,
            body: r.body() || '',
            completed: r.completed(),
            priority: r.priority()
        }});
    }});

    if (results.length === 0) return '列表「{escaped_list}」中没有提醒事项';

    return results.map(r => {{
        const status = r.completed ? '✅' : '⬜';
        let line = `${{status}} ${{r.name}}`;
        if (r.date) line += ` [${{r.date}}]`;
        if (r.body) line += ` — ${{r.body}}`;
        return line;
    }}).join('\\n');
}})()
"""
    ok, msg = _run_jxa(script)
    if not ok:
        return f"查询失败: {msg}"
    return msg


@mcp.tool()
def reminders_search(keyword: str) -> str:
    """在所有列表中搜索提醒事项。

    Args:
        keyword: 搜索关键词
    """
    escaped_kw = _escape_jxa(keyword)

    script = f"""
(() => {{
    const app = Application('Reminders');
    const kw = '{escaped_kw}'.toLowerCase();
    const results = [];

    app.lists().forEach(list => {{
        list.reminders.whose({{completed: false}})().forEach(r => {{
            const name = r.name() || '';
            const body = r.body() || '';
            if (name.toLowerCase().includes(kw) || body.toLowerCase().includes(kw)) {{
                const dd = r.dueDate();
                let dateStr = '';
                if (dd) {{
                    dateStr = dd.getFullYear() + '-' +
                        (dd.getMonth()+1).toString().padStart(2,'0') + '-' +
                        dd.getDate().toString().padStart(2,'0') + ' ' +
                        dd.getHours().toString().padStart(2,'0') + ':' +
                        dd.getMinutes().toString().padStart(2,'0');
                }}
                results.push({{
                    name: name,
                    date: dateStr,
                    list: list.name(),
                    body: body
                }});
            }}
        }});
    }});

    if (results.length === 0) return '未找到包含「{escaped_kw}」的提醒事项';

    return results.map(r => {{
        let line = `⬜ ${{r.name}}`;
        if (r.date) line += ` [${{r.date}}]`;
        line += ` (${{r.list}})`;
        if (r.body) line += ` — ${{r.body}}`;
        return line;
    }}).join('\\n');
}})()
"""
    ok, msg = _run_jxa(script)
    if not ok:
        return f"搜索失败: {msg}"
    return msg


@mcp.tool()
def reminders_show_lists() -> str:
    """显示所有提醒事项列表及其未完成任务数。"""
    script = """
(() => {
    const app = Application('Reminders');
    return app.lists().map(list => {
        const count = list.reminders.whose({completed: false})().length;
        return `${list.name()} (${count})`;
    }).join('\\n');
})()
"""
    ok, msg = _run_jxa(script)
    if not ok:
        return f"查询失败: {msg}"
    return msg


if __name__ == "__main__":
    mcp.run()
