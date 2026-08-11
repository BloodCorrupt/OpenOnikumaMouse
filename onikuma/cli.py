"""
Onikuma CW935 Interactive CLI
==============================
Rich terminal UI for configuring DPI, buttons, lighting, and performance settings.
"""

import sys
import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich.align import Align
from rich import box

from .mouse import OnikumaCW935
from .protocol import (
    LightMode, ReportRate, BUTTON_PRESETS, BUTTON_LABELS,
    DPI_MIN, DPI_MAX, DPI_STEP
)

console = Console()


def print_header():
    """Display app banner."""
    grid = Table.grid(expand=True)
    grid.add_column(justify="center")
    grid.add_row(
        "[bold cyan]ONIKUMA CW935 MOUSE CONTROLLER[/bold cyan]"
    )
    grid.add_row(
        "[dim]Custom Python Driver & Configuration Utility (Instant S203 Sensor)[/dim]"
    )
    console.print(Panel(grid, style="bold blue", border_style="cyan"))


def format_battery(percentage: int, charging: bool) -> str:
    """Format battery status string with colors."""
    status = " [charging]" if charging else ""
    if percentage > 60:
        color = "green"
    elif percentage > 20:
        color = "yellow"
    else:
        color = "red"
    return f"[{color}]{percentage}%[/] {status}"


def display_dashboard(mouse: OnikumaCW935):
    """Display current mouse status overview in a compact dashboard."""
    try:
        info = mouse.get_info()
        battery = mouse.get_battery()
        config = mouse.get_config()
        buttons = mouse.get_buttons()
    except Exception as e:
        console.print(f"[bold red]Error reading mouse status:[/] {e}")
        return

    # Header info table
    info_table = Table(show_header=False, box=box.SIMPLE, expand=True)
    info_table.add_column("Key", style="bold dim", width=20)
    info_table.add_column("Value", style="bold white")

    info_table.add_row("Firmware Version:", f"[green]{info.firmware_version}[/green]")
    info_table.add_row("Connection Mode:", f"[cyan]{info.connection_mode}[/cyan]")
    info_table.add_row("Battery Level:", format_battery(battery.percentage, battery.charging))

    # DPI & Performance
    active_dpi = config.active_dpi
    stages_str = ", ".join(
        f"[bold cyan]<{v}>[/bold cyan]" if i == config.dpi_index else f"[dim]{v}[/dim]"
        for i, v in enumerate(config.dpi_values[:config.dpi_count])
    )

    info_table.add_row("Active DPI:", f"[bold yellow]{active_dpi} DPI[/bold yellow] (Stage {config.dpi_index + 1}/{config.dpi_count})")
    info_table.add_row("DPI Stages:", stages_str)
    info_table.add_row("Report Rate:", f"[green]{config.report_rate_hz} Hz[/green]")
    info_table.add_row("Lighting Mode:", f"[magenta]Mode {config.light_mode}[/magenta]")
    info_table.add_row("Lift-Off Distance:", "Low (1mm)" if config.lod_value == 1 else "High (2mm)")
    info_table.add_row("Debounce Time:", f"{config.key_respond} ms")
    info_table.add_row("Sleep Timeout:", f"{config.sleep_time} min" if config.sleep_time else "Disabled")

    console.print(Panel(info_table, title="[bold white]Device Status[/bold white]", border_style="blue"))

    # Button Summary Table
    btn_table = Table(title="Button Assignments", box=box.ROUNDED, expand=True)
    btn_table.add_column("#", style="dim", width=4, justify="center")
    btn_table.add_column("Button", style="cyan", width=18)
    btn_table.add_column("Function / Mapping", style="bold green")

    for i, btn in enumerate(buttons):
        label = BUTTON_LABELS[i] if i < len(BUTTON_LABELS) else f"Button {i+1}"
        btn_table.add_row(str(i+1), label, btn.description)

    console.print(btn_table)


def menu_dpi_control(mouse: OnikumaCW935):
    """Submenu for DPI settings."""
    while True:
        console.clear()
        print_header()
        config = mouse.get_config()

        console.print(Panel("[bold yellow]DPI CONTROL (50 - 12,800 DPI)[/bold yellow]", style="yellow"))

        table = Table(box=box.SIMPLE_HEAD)
        table.add_column("Stage #", justify="center", style="bold cyan")
        table.add_column("DPI Value", justify="right")
        table.add_column("Status", justify="center")

        for i, val in enumerate(config.dpi_values[:config.dpi_count]):
            is_active = (i == config.dpi_index)
            status = "[bold green]ACTIVE[/bold green]" if is_active else "[dim]Inactive[/dim]"
            val_str = f"[bold yellow]{val}[/bold yellow]" if is_active else str(val)
            table.add_row(str(i + 1), val_str, status)

        console.print(table)
        console.print("\nOptions:")
        console.print("  [1] Set active DPI stage")
        console.print("  [2] Configure all DPI stages")
        console.print("  [3] Set DPI count (1 - 6 stages)")
        console.print("  [4] Quick set active DPI value")
        console.print("  [0] Back to Main Menu")

        choice = Prompt.ask("\nSelect an option", choices=["0", "1", "2", "3", "4"], default="0")

        if choice == "0":
            break
        elif choice == "1":
            stage = IntPrompt.ask("Enter stage number to activate", min=1, max=config.dpi_count)
            mouse.set_active_dpi_stage(stage - 1)
            console.print(f"[green]Activated DPI Stage {stage}![/green]")
            time.sleep(1)
        elif choice == "2":
            new_stages = []
            count = config.dpi_count
            console.print(f"\nEnter new values for {count} DPI stages (between 50 and 12800):")
            for i in range(count):
                cur = config.dpi_values[i] if i < len(config.dpi_values) else 800
                val = IntPrompt.ask(f"  Stage {i+1} DPI", default=cur, min=DPI_MIN, max=DPI_MAX)
                new_stages.append(val)
            mouse.set_dpi_stages(new_stages, active_index=config.dpi_index)
            console.print("[bold green]DPI stages updated successfully![/bold green]")
            time.sleep(1.5)
        elif choice == "3":
            count = IntPrompt.ask("Enter number of active stages", min=1, max=6, default=config.dpi_count)
            stages = config.dpi_values[:count]
            active = min(config.dpi_index, count - 1)
            mouse.set_dpi_stages(stages, active_index=active)
            console.print(f"[green]DPI stages set to {count}![/green]")
            time.sleep(1)
        elif choice == "4":
            dpi = IntPrompt.ask("Enter DPI value for current stage", min=DPI_MIN, max=DPI_MAX, default=config.active_dpi)
            mouse.set_quick_dpi(dpi)
            console.print(f"[green]Active DPI set to {dpi}![/green]")
            time.sleep(1)


def menu_lighting(mouse: OnikumaCW935):
    """Submenu for Lighting settings."""
    while True:
        console.clear()
        print_header()
        config = mouse.get_config()

        console.print(Panel(f"[bold magenta]LIGHTING CONTROL (Current Mode: {config.light_mode})[/bold magenta]", style="magenta"))

        table = Table(box=box.SIMPLE)
        table.add_column("Mode ID", style="bold cyan", justify="center")
        table.add_column("Effect Name", style="white")

        modes = [
            (0, "Off (LED Disabled)"),
            (1, "Breathing (Multi-color)"),
            (2, "Neon / Color Cycle"),
            (3, "Static / Constant"),
            (4, "Single Color Breathing"),
            (5, "Reactive Click"),
            (6, "Rainbow Wave"),
            (7, "Colorful Streaming"),
        ]

        for mode_id, name in modes:
            style = "bold green" if mode_id == config.light_mode else "white"
            active_mark = " (Active)" if mode_id == config.light_mode else ""
            table.add_row(str(mode_id), f"[{style}]{name}{active_mark}[/{style}]")

        console.print(table)
        console.print("\n[dim]Note: You can also enter higher mode numbers (8-15) if supported by firmware.[/dim]")
        console.print("  [0-15] Enter mode ID directly")
        console.print("  [b]    Back to Main Menu")

        choice = Prompt.ask("\nSelect mode ID or option", default="b")

        if choice.lower() == 'b':
            break
        elif choice.isdigit():
            mode_val = int(choice)
            if 0 <= mode_val <= 15:
                mouse.set_light_mode(mode_val)
                console.print(f"[bold green]Applied Light Mode {mode_val}![/bold green]")
                time.sleep(1)


def menu_button_mapping(mouse: OnikumaCW935):
    """Submenu for button remapping."""
    while True:
        console.clear()
        print_header()
        buttons = mouse.get_buttons()

        console.print(Panel("[bold green]BUTTON PROGRAMMING[/bold green]", style="green"))

        table = Table(box=box.ROUNDED, expand=True)
        table.add_column("#", style="bold cyan", justify="center", width=4)
        table.add_column("Physical Button", style="bold white", width=18)
        table.add_column("Current Mapping", style="bold green")

        for i, btn in enumerate(buttons):
            label = BUTTON_LABELS[i] if i < len(BUTTON_LABELS) else f"Button {i+1}"
            table.add_row(str(i + 1), label, btn.description)

        console.print(table)
        console.print("\nOptions:")
        console.print("  [1-6] Reassign specific button")
        console.print("  [r]   Reset all buttons to default")
        console.print("  [0]   Back to Main Menu")

        choice = Prompt.ask("\nSelect option", default="0")

        if choice == "0":
            break
        elif choice.lower() == 'r':
            if Confirm.ask("Reset all buttons to factory defaults?"):
                mouse.reset_buttons()
                console.print("[green]Buttons reset to default![/green]")
                time.sleep(1)
        elif choice.isdigit() and 1 <= int(choice) <= 6:
            btn_idx = int(choice) - 1
            btn_label = BUTTON_LABELS[btn_idx]

            console.print(f"\n[bold yellow]Select Preset for {btn_label}:[/bold yellow]")
            presets_list = list(BUTTON_PRESETS.keys())
            for idx, p_name in enumerate(presets_list, 1):
                desc = p_name.replace("_", " ").title()
                console.print(f"  [{idx:2d}] {desc}")

            p_choice = IntPrompt.ask("\nSelect preset", min=1, max=len(presets_list))
            selected_preset = presets_list[p_choice - 1]

            mouse.set_button_preset(btn_idx, selected_preset)
            console.print(f"[bold green]Set {btn_label} to '{selected_preset.replace('_', ' ').title()}'![/bold green]")
            time.sleep(1.5)


def menu_performance(mouse: OnikumaCW935):
    """Submenu for polling rate, LOD, debounce, etc."""
    while True:
        console.clear()
        print_header()
        config = mouse.get_config()

        console.print(Panel("[bold cyan]PERFORMANCE & HARDWARE SETTINGS[/bold cyan]", style="cyan"))

        table = Table(box=box.SIMPLE_HEAD)
        table.add_column("Setting", style="bold white")
        table.add_column("Current Value", style="bold yellow")
        table.add_column("Description", style="dim")

        table.add_row("Report Rate", f"{config.report_rate_hz} Hz", "USB polling frequency (125 - 1000Hz)")
        table.add_row("Lift-Off Distance (LOD)", f"Level {config.lod_value} ({'Low' if config.lod_value==1 else 'High'})", "Sensor tracking height cutoff")
        table.add_row("Button Debounce", f"{config.key_respond} ms", "Key response delay (debounce)")
        table.add_row("Sleep Timeout", f"{config.sleep_time} min" if config.sleep_time else "Disabled", "Inactivity sleep timer")
        table.add_row("Scroll Direction", "Inverted" if config.scroll_flag else "Normal", "Mouse wheel direction")

        console.print(table)
        console.print("\nOptions:")
        console.print("  [1] Set Report Rate (125Hz, 250Hz, 500Hz, 1000Hz)")
        console.print("  [2] Set Lift-Off Distance (1 = Low, 2 = High)")
        console.print("  [3] Set Button Debounce (1 - 30 ms)")
        console.print("  [4] Set Auto-Sleep Timeout (0 - 30 min)")
        console.print("  [0] Back to Main Menu")

        choice = Prompt.ask("\nSelect option", choices=["0", "1", "2", "3", "4"], default="0")

        if choice == "0":
            break
        elif choice == "1":
            rate = IntPrompt.ask("Enter polling rate (125, 250, 500, 1000)", default=config.report_rate_hz)
            if rate in (125, 250, 500, 1000):
                mouse.set_report_rate(rate)
                console.print(f"[green]Report rate set to {rate}Hz![/green]")
                time.sleep(1)
            else:
                console.print("[red]Invalid rate! Must be 125, 250, 500, or 1000.[/red]")
                time.sleep(1)
        elif choice == "2":
            lod = IntPrompt.ask("Enter LOD level (1 = Low, 2 = High)", min=1, max=2, default=config.lod_value)
            mouse.set_lod(lod)
            console.print(f"[green]LOD set to Level {lod}![/green]")
            time.sleep(1)
        elif choice == "3":
            ms = IntPrompt.ask("Enter debounce time in ms", min=1, max=30, default=config.key_respond)
            mouse.set_debounce(ms)
            console.print(f"[green]Debounce time set to {ms}ms![/green]")
            time.sleep(1)
        elif choice == "4":
            mins = IntPrompt.ask("Enter sleep timeout in minutes (0 = Off)", min=0, max=30, default=config.sleep_time)
            mouse.set_sleep_timer(mins)
            console.print(f"[green]Sleep timer set to {mins} min![/green]")
            time.sleep(1)


def run_cli(mouse: OnikumaCW935):
    """Main CLI loop."""
    while True:
        console.clear()
        print_header()
        display_dashboard(mouse)

        console.print("\n[bold white]MAIN MENU[/bold white]")
        console.print("  [1] DPI Control (Stages, active stage, custom DPI)")
        console.print("  [2] RGB Lighting Effects")
        console.print("  [3] Button Programming & Remapping")
        console.print("  [4] Performance Settings (Polling rate, LOD, Debounce)")
        console.print("  [R] Factory Reset")
        console.print("  [Q] Exit")

        choice = Prompt.ask("\nSelect an option", default="1")

        if choice.lower() in ('q', 'quit', 'exit'):
            console.print("\n[bold cyan]Exiting Onikuma CW935 Mouse Controller. Goodbye![/bold cyan]")
            break
        elif choice == "1":
            menu_dpi_control(mouse)
        elif choice == "2":
            menu_lighting(mouse)
        elif choice == "3":
            menu_button_mapping(mouse)
        elif choice == "4":
            menu_performance(mouse)
        elif choice.lower() == 'r':
            if Confirm.ask("[bold red]Are you sure you want to restore ALL factory defaults?[/bold red]"):
                mouse.factory_reset()
                console.print("[bold green]Mouse restored to factory defaults![/bold green]")
                time.sleep(1.5)
