import schedule
import time
import threading
from plyer import notification
import tkinter as tk
import ttkbootstrap as ttk
from tkinter import simpledialog, messagebox
import pystray
from PIL import Image, ImageDraw
import os

# Store reminders so we can stop them
active_reminders = []

class ReminderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reminder")
        self.root.geometry("500x400")
        
        # Make window appear on top initially
        self.root.attributes('-topmost', True)
        self.root.after(1000, lambda: self.root.attributes('-topmost', False))
        
        self.setup_ui()
        
        # Start scheduler in background
        self.scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # Setup system tray (minimize to tray)
        self.setup_tray()
        
        # Bind window close to minimize to tray
        self.root.protocol('WM_DELETE_WINDOW', self.minimize_to_tray)

    def setup_ui(self):
        # Header
        header_frame = ttk.Frame(self.root, height=80, style='primary.TFrame')
        header_frame.pack(fill='x', padx=10, pady=10)
        header_frame.pack_propagate(False)
        
        ttk.Label(header_frame, text="🔔 Reminder", font=("Arial", 16, "bold"), 
                 style='inverse-primary.TLabel').pack(expand=True)
        
        ttk.Label(header_frame, text="Never forget anything again!", font=("Arial", 10), 
                 style='inverse-primary.TLabel').pack(expand=True)

        # Quick Actions Frame
        actions_frame = ttk.Frame(self.root)
        actions_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(actions_frame, text="➕ New Reminder", command=self.schedule_reminder, style='success.TButton').pack(side='left', padx=5, ipady=5)
        ttk.Button(actions_frame, text="⏹️ Stop All", command=self.stop_all_reminders, style='danger.TButton').pack(side='left', padx=5, ipady=5)
        ttk.Button(actions_frame, text="🔄 Refresh", command=self.refresh_reminders, style='info.TButton').pack(side='left', padx=5, ipady=5)
        ttk.Button(actions_frame, text="❌ Quit app", command=self.kill_app, style='exit.TButton').pack(side='left', padx=5, ipady=5)
        
        # Active Reminders Frame
        reminders_frame = ttk.Labelframe(self.root, text="Active Reminders", style='info.TLabelframe', padding=(10, 5))
        reminders_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Treeview for reminders
        columns = ('message', 'interval', 'actions')
        self.reminder_tree = ttk.Treeview(reminders_frame, columns=columns, show='headings', height=8)
        
        self.reminder_tree.heading('message', text='Reminder Message')
        self.reminder_tree.heading('interval', text='Interval (min)')
        self.reminder_tree.heading('actions', text='Actions')
        
        self.reminder_tree.column('message', width=300)
        self.reminder_tree.column('interval', width=100)
        self.reminder_tree.column('actions', width=100)
        
        self.reminder_tree.pack(fill='both', expand=True)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, style='inverse-primary.TLabel', font=("Arial", 9), anchor='w', padding=(10, 2))
        status_bar.pack(fill='x', side='bottom')

    def schedule_reminder(self):
        """Open dialog to create new reminder"""
        message = simpledialog.askstring("New Reminder", "What would you like to be reminded of?")
        if not message:
            return

        interval = simpledialog.askfloat("New Reminder", "In how many minutes?")
        if not interval:
            return

        # Create a unique ID for this reminder
        job_id = f"reminder_{len(active_reminders)}"
        job = schedule.every(interval).minutes.do(self.send_reminder, message=message, job_id=job_id)
        
        # Store reminder info
        active_reminders.append({
            'id': job_id,
            'message': message,
            'interval': interval,
            'job': job
        })
        
        messagebox.showinfo("Reminder Set", f"Reminding you to '{message}' every {interval} minutes.")
        self.refresh_reminders()
        self.status_var.set(f"Reminder added: '{message}' every {interval} minutes")

    def send_reminder(self, message, job_id):
        """Send notification and update status"""
        try:
            notification.notify(
                title="Reminder!",
                message=message,
                app_name="Python Reminder",
                timeout=10
            )
            self.status_var.set(f"Reminder sent: '{message}'")
            print(f"Reminder sent: '{message}'")
        except Exception as e:
            # Fallback to messagebox if notification fails
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Reminder!", message)
            root.destroy()

    def stop_all_reminders(self):
        """Stop all active reminders"""
        if not active_reminders:
            messagebox.showinfo("Info", "No active reminders to stop!")
            return
            
        schedule.clear()
        active_reminders.clear()
        self.refresh_reminders()
        self.status_var.set("All reminders stopped!")
        messagebox.showinfo("Success", "All reminders have been stopped!")

    def stop_single_reminder(self, job_id):
        """Stop a specific reminder"""
        reminder_to_remove = None
        for reminder in active_reminders:
            if reminder['id'] == job_id:
                reminder_to_remove = reminder
                break
        
        if reminder_to_remove:
            schedule.cancel_job(reminder_to_remove['job'])
            active_reminders.remove(reminder_to_remove)
            self.refresh_reminders()
            self.status_var.set(f"Stopped reminder: '{reminder_to_remove['message']}'")

    def refresh_reminders(self):
        """Refresh the reminders list"""
        # Clear existing items
        for item in self.reminder_tree.get_children():
            self.reminder_tree.delete(item)
        
        # Add current reminders
        for reminder in active_reminders:
            self.reminder_tree.insert('', 'end', values=(
                reminder['message'],
                reminder['interval'],
                'Stop'
            ), tags=(reminder['id'],))
        
        # Bind click event to stop buttons
        self.reminder_tree.bind('<ButtonRelease-1>', self.on_tree_click)
        
        # Update status
        count = len(active_reminders)
        self.status_var.set(f"Active reminders: {count}")

    def on_tree_click(self, event):
        """Handle clicks on the treeview"""
        item = self.reminder_tree.identify_row(event.y)
        column = self.reminder_tree.identify_column(event.x)
        
        if item and column == '#3':  # Actions column
            job_id = self.reminder_tree.item(item)['tags'][0]
            self.stop_single_reminder(job_id)

    def run_scheduler(self):
        """Run the schedule checker in background"""
        while True:
            schedule.run_pending()
            time.sleep(1)

    def create_image(self):
        """Create system tray icon"""
        img = Image.new('RGB', (64, 64), color=(44, 62, 80))
        d = ImageDraw.Draw(img)
        d.rectangle((16, 16, 48, 48), fill=(231, 76, 60))
        d.ellipse((20, 20, 44, 44), fill=(255, 255, 255))
        return img

    def setup_tray(self):
        """Setup system tray icon"""
        image = self.create_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show App", self.show_app),
            pystray.MenuItem("New Reminder", self.schedule_reminder),
            pystray.MenuItem("Stop All Reminders", self.stop_all_reminders),
            pystray.MenuItem("Quit", self.quit_app)
        )
        self.tray_icon = pystray.Icon("Reminder", image, "Python Reminder", menu)
        
        # Start tray in background thread
        tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        tray_thread.start()

    def show_app(self, icon=None, item=None):
        """Show the main application window"""
        self.root.after(0, self.restore_window)
    
    def kill_app(self):
        """End the application"""
        self.root.quit()

    def restore_window(self):
        """Restore and focus the main window"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes('-topmost', True)
        self.root.after(1000, lambda: self.root.attributes('-topmost', False))

    def minimize_to_tray(self):
        """Minimize to system tray"""
        self.root.withdraw()

    def quit_app(self, icon=None, item=None):
        """Quit the application completely"""
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.quit()
        os._exit(0)

def main():
    root = ttk.Window(themename="darkly")
    app = ReminderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()