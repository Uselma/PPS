from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import datetime
import pywhatkit
import sqlite3
import tkinter as tk
from tkinter import messagebox
import pyautogui
import time

class Schedule:
    def __init__(self):
        # Define available days and hours for scheduling
        self.days = ['mon', 'tue', 'wed', 'thu', 'fri'] # Monday to Friday
        self.hours = range(1, 11) # 10-hour schedule
        self.co2_threshold = None # Threshold for CO₂ levels


    def check_co2_levels(self, schedule_data):
        co2_data = self.scrape_co2_data()

        now = datetime.datetime.now()
        # Get current day and hour
        current_day = now.strftime("%a").lower()[:3] # Convert day to lowercase and short form
        current_hour = now.hour

         # Find the current classroom based on the schedule
        current_classroom = None
        if current_day in schedule_data:
            for lesson in schedule_data[current_day]:
                if lesson is not None and lesson[0] == current_hour:
                    current_classroom = lesson[1]
                    break

        print(f"🎯 Looking for room number: {current_classroom}")

        # Match classroom from scraped CO₂ data
        matched_classroom = None
        for room_name in co2_data:
            if current_classroom and current_classroom in room_name:
                matched_classroom = room_name
                break

         # Check if CO₂ level exceeds threshold
        if matched_classroom:
            co2_level = co2_data[matched_classroom]
            if co2_level > self.co2_threshold:
                print(f"⚠️ {matched_classroom}: {co2_level} ppm > threshold {self.co2_threshold}")
                phone_number = get_saved_phone_number()
                message = f"⚠️ CO₂ in {matched_classroom} is {co2_level} ppm! (Limit: {self.co2_threshold})"
                pywhatkit.sendwhatmsg_instantly(phone_number, message) # Send alert via WhatsApp
                time.sleep(10)
                pyautogui.press("enter")  # Ensure message is sent
                print("📤 WhatsApp message sent.")
            else:
                print(f"{matched_classroom}: {co2_level} ppm is safe.")
        else:
            print("❌ No matching classroom found in CO₂ data.")

    def calculate_start_time(self, hour):
        if hour == 1:
            return datetime.time(8, 15)
        elif hour == 2:
            return datetime.time(9, 0)
        elif hour == 3:
            return datetime.time(9, 45)
        elif hour == 4:
            return datetime.time(10, 45)
        elif hour == 5:
            return datetime.time(11, 45)
        elif hour == 6:
            return datetime.time(12, 30)
        elif hour == 7:
            return datetime.time(13, 15)
        elif hour == 8:
            return datetime.time(14, 0)
        elif hour == 9:
            return datetime.time(14, 45)
        elif hour == 10:
            return datetime.time(15, 30)
        else:
            return None

    def scrape_co2_data(self):
        url = "https://co2.mesh.lv/home/building-devices/1038" # Website containing CO₂ data
        options = Options()
        options.add_argument("--headless") # Run browser in headless mode
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)

        print("\n🌐 Scraping CO₂ data from live site...")
        driver.get(url)
        time.sleep(5) # Allow page to load


        co2_data = {}
        try:
            rows = driver.find_elements(By.XPATH, "//table//tbody//tr") # Extract table rows
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td") # Extract table columns
                if len(cols) >= 2:
                    room = cols[0].text.strip() # Room name
                    co2 = cols[1].text.strip() # CO₂ level
                    try:
                        co2_value = int(co2)
                        co2_data[room] = co2_value
                    except ValueError:
                        continue  # Ignore invalid data
        finally:
            driver.quit()

        print("✅ Scraping complete.\n")
        return co2_data


class ScheduleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CO₂ Monitoring Schedule")

         # Initialize schedule data
        self.schedule_data = {day: [] for day in ['mon', 'tue', 'wed', 'thu', 'fri']}
        self.co2_threshold = None
        self.phone_number = None

        self.schedule = Schedule()
        self.initialize_database()

        # UI Components
        self.canvas = tk.Canvas(root)
        self.scrollbar = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.schedule_label = tk.Label(self.scrollable_frame, text="Enter your weekly schedule")
        self.schedule_label.grid(row=0, column=0, columnspan=2)

        self.day_entries = {} # Store user input fields
        row_counter = 1

        # Create input fields for each day and hour
        for day in self.schedule.days:
            tk.Label(self.scrollable_frame, text=day.capitalize()).grid(row=row_counter, column=0, pady=5)
            self.day_entries[day] = []
            for hour in self.schedule.hours:
                tk.Label(self.scrollable_frame, text=f"Hour {hour}:").grid(row=row_counter + hour, column=0)
                entry = tk.Entry(self.scrollable_frame)
                entry.grid(row=row_counter + hour, column=1)
                self.day_entries[day].append(entry)
            row_counter += len(self.schedule.hours) + 2

        # Threshold and phone number input fields
        self.threshold_label = tk.Label(self.scrollable_frame, text="CO₂ threshold (ppm):")
        self.threshold_label.grid(row=row_counter, column=0)
        self.threshold_entry = tk.Entry(self.scrollable_frame)
        self.threshold_entry.grid(row=row_counter, column=1)

        self.phone_label = tk.Label(self.scrollable_frame, text="Phone number (+countrycode...):")
        self.phone_label.grid(row=row_counter + 1, column=0)
        self.phone_entry = tk.Entry(self.scrollable_frame)
        self.phone_entry.grid(row=row_counter + 1, column=1)

        # Buttons for saving and checking schedule
        self.save_button = tk.Button(self.scrollable_frame, text="Save Schedule", command=self.save_schedule)
        self.save_button.grid(row=row_counter + 2, column=0, pady=10)

        self.set_threshold_button = tk.Button(self.scrollable_frame, text="Set CO₂ Threshold", command=self.set_co2_threshold)
        self.set_threshold_button.grid(row=row_counter + 2, column=1)

        self.check_button = tk.Button(self.scrollable_frame, text="Check Now", command=self.check_now)
        self.check_button.grid(row=row_counter + 3, column=0, columnspan=2)

    # Initialize the database tables if they do not exist
    def initialize_database(self):
         # Connect to the SQLite database
        conn = sqlite3.connect('co2_data.db')
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS schedule (day TEXT, hour INTEGER, classroom TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS co2_threshold (threshold INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS phone_numbers (phone_number TEXT)")
        # Commit the changes and close the connection
        conn.commit()
        conn.close()

    # Save the schedule data to the database
    def save_schedule(self):
        self.schedule_data = {day: [] for day in self.schedule.days}
         # Iterate over the day entries and extract the classroom data
        for day, entries in self.day_entries.items():
            for hour_idx, entry in enumerate(entries, start=1):
                classroom = entry.get().strip()
                if classroom:
                    # Normalize single-digit numbers to two digits (e.g., "2" -> "02")
                    if classroom.isdigit() and len(classroom) == 1:
                        classroom = f"0{classroom}"
                    self.schedule_data[day].append((hour_idx, classroom))
                else:
                    self.schedule_data[day].append(None)
        # Store the schedule data in the database
        store_schedule(self.schedule_data)
        # Show a message box to confirm that the schedule was saved
        messagebox.showinfo("Saved", "Schedule saved successfully!")

    # Set the CO2 threshold and phone number
    def set_co2_threshold(self):
        try:
            threshold = int(self.threshold_entry.get())
            if threshold < 0:
                raise ValueError
            self.co2_threshold = threshold
            store_co2_threshold(threshold)
            store_phone_number(self.phone_entry.get().strip())
            messagebox.showinfo("Saved", "Threshold and phone number saved!")
        except:
            messagebox.showerror("Invalid", "Enter a valid non-negative threshold.")

    # Check the CO2 levels
    def check_now(self):
        self.schedule.co2_threshold = get_saved_threshold()
        self.schedule.check_co2_levels(self.schedule_data)

# Database functions

# Store the schedule data in the database
def store_schedule(data):
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM schedule")
    for day, lessons in data.items():
        for lesson in lessons:
            if lesson:
                cur.execute("INSERT INTO schedule VALUES (?, ?, ?)", (day, lesson[0], lesson[1]))
    conn.commit()
    conn.close()

# Store the CO2 threshold in the database
def store_co2_threshold(thresh):
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM co2_threshold")
    cur.execute("INSERT INTO co2_threshold VALUES (?)", (thresh,))
    conn.commit()
    conn.close()

# Store the phone number in the database
def store_phone_number(phone):
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM phone_numbers")
    cur.execute("INSERT INTO phone_numbers VALUES (?)", (phone,))
    conn.commit()
    conn.close()

# Get the saved CO2 threshold
def get_saved_threshold():
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("SELECT threshold FROM co2_threshold")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 1000

#Get the saved phone number
def get_saved_phone_number():
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("SELECT phone_number FROM phone_numbers")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "+37112345678"

# Main
if __name__ == "__main__":
    root = tk.Tk()
    app = ScheduleApp(root)
    root.mainloop()
