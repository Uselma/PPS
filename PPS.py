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
        self.days = ['mon', 'tue', 'wed', 'thu', 'fri']
        self.hours = range(1, 11)
        self.co2_threshold = None

    def check_co2_levels(self, schedule_data):
        co2_data = self.scrape_co2_data()

        now = datetime.datetime.now()

        current_day = now.strftime("%a").lower()[:3]
        current_hour = now.hour

        current_classroom = None
        if current_day in schedule_data:
            for lesson in schedule_data[current_day]:
                if lesson is not None and lesson[0] == current_hour:
                    current_classroom = lesson[1]
                    break

        print(f"🎯 Looking for room number: {current_classroom}")

        matched_classroom = None
        for room_name in co2_data:
            if current_classroom and current_classroom in room_name:
                matched_classroom = room_name
                break

        if matched_classroom:
            co2_level = co2_data[matched_classroom]
            if co2_level > self.co2_threshold:
                print(f"⚠️ {matched_classroom}: {co2_level} ppm > threshold {self.co2_threshold}")
                phone_number = get_saved_phone_number()
                message = f"⚠️ CO₂ in {matched_classroom} is {co2_level} ppm! (Limit: {self.co2_threshold})"
                pywhatkit.sendwhatmsg_instantly(phone_number, message)
                time.sleep(10)
                pyautogui.press("enter")
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
        url = "https://co2.mesh.lv/home/building-devices/1038"
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)

        print("\n🌐 Scraping CO₂ data from live site...")
        driver.get(url)
        time.sleep(5)

        co2_data = {}
        try:
            rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) >= 2:
                    room = cols[0].text.strip()
                    co2 = cols[1].text.strip()
                    try:
                        co2_value = int(co2)
                        co2_data[room] = co2_value
                    except ValueError:
                        continue
        finally:
            driver.quit()

        print("✅ Scraping complete.\n")
        return co2_data


class ScheduleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CO₂ Monitoring Schedule")

        self.schedule_data = {day: [] for day in ['mon', 'tue', 'wed', 'thu', 'fri']}
        self.co2_threshold = None
        self.phone_number = None

        self.schedule = Schedule()
        self.initialize_database()

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

        self.day_entries = {}
        row_counter = 1

        for day in self.schedule.days:
            tk.Label(self.scrollable_frame, text=day.capitalize()).grid(row=row_counter, column=0, pady=5)
            self.day_entries[day] = []
            for hour in self.schedule.hours:
                tk.Label(self.scrollable_frame, text=f"Hour {hour}:").grid(row=row_counter + hour, column=0)
                entry = tk.Entry(self.scrollable_frame)
                entry.grid(row=row_counter + hour, column=1)
                self.day_entries[day].append(entry)
            row_counter += len(self.schedule.hours) + 2

        self.threshold_label = tk.Label(self.scrollable_frame, text="CO₂ threshold (ppm):")
        self.threshold_label.grid(row=row_counter, column=0)
        self.threshold_entry = tk.Entry(self.scrollable_frame)
        self.threshold_entry.grid(row=row_counter, column=1)

        self.phone_label = tk.Label(self.scrollable_frame, text="Phone number (+countrycode...):")
        self.phone_label.grid(row=row_counter + 1, column=0)
        self.phone_entry = tk.Entry(self.scrollable_frame)
        self.phone_entry.grid(row=row_counter + 1, column=1)

        self.save_button = tk.Button(self.scrollable_frame, text="Save Schedule", command=self.save_schedule)
        self.save_button.grid(row=row_counter + 2, column=0, pady=10)

        self.set_threshold_button = tk.Button(self.scrollable_frame, text="Set CO₂ Threshold", command=self.set_co2_threshold)
        self.set_threshold_button.grid(row=row_counter + 2, column=1)

        self.check_button = tk.Button(self.scrollable_frame, text="Check Now", command=self.check_now)
        self.check_button.grid(row=row_counter + 3, column=0, columnspan=2)

    def initialize_database(self):
        conn = sqlite3.connect('co2_data.db')
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS schedule (day TEXT, hour INTEGER, classroom TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS co2_threshold (threshold INTEGER)")
        cur.execute("CREATE TABLE IF NOT EXISTS phone_numbers (phone_number TEXT)")
        conn.commit()
        conn.close()

    def save_schedule(self):
        self.schedule_data = {day: [] for day in self.schedule.days}
        for day, entries in self.day_entries.items():
            for hour_idx, entry in enumerate(entries, start=1):
                classroom = entry.get().strip()
                if classroom:
                    if classroom.isdigit() and len(classroom) == 1:
                        classroom = f"0{classroom}"
                    self.schedule_data[day].append((hour_idx, classroom))
                else:
                    self.schedule_data[day].append(None)
        store_schedule(self.schedule_data)
        messagebox.showinfo("Saved", "Schedule saved successfully!")

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

    def check_now(self):
        self.schedule.co2_threshold = get_saved_threshold()
        self.schedule.check_co2_levels(self.schedule_data)

# Database functions
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

def store_co2_threshold(thresh):
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM co2_threshold")
    cur.execute("INSERT INTO co2_threshold VALUES (?)", (thresh,))
    conn.commit()
    conn.close()

def store_phone_number(phone):
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("DELETE FROM phone_numbers")
    cur.execute("INSERT INTO phone_numbers VALUES (?)", (phone,))
    conn.commit()
    conn.close()

def get_saved_threshold():
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("SELECT threshold FROM co2_threshold")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 1000

def get_saved_phone_number():
    conn = sqlite3.connect('co2_data.db')
    cur = conn.cursor()
    cur.execute("SELECT phone_number FROM phone_numbers")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "+37112345678"

if __name__ == "__main__":
    root = tk.Tk()
    app = ScheduleApp(root)
    root.mainloop()
