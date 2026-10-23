import time

# ==========================================
# CT SCAN COMPANION / CT-BEGLEITER
# ==========================================

TEXT = {
    "en": {
        "welcome": "Hello! I am your CT Scan Companion robot.",
        "questions": [
            "Have you ever had an allergic reaction to CT contrast material?",
            "Do you have kidney problems?",
            "Are you pregnant or could you be pregnant?",
            "Do you have a pacemaker, implant, or medication pump?",
            "Are you wearing jewellery, piercings, or metal objects?",
            "Do you have removable dental appliances or other removable items?",
            "Are there medicines or special instructions the radiology team should know about?",
            "Are you anxious or afraid about the CT scan?",
            "Do you need help walking or getting onto the CT table?",
            "Do you need language or communication assistance?"
        ],
        "screening": "Before we begin, I need to ask some safety questions.",
        "answer": "Enter 1 for Yes, 2 for No, or 3 for Not sure:",
        "pause": "We must pause here. The radiology team needs to review your answer.",
        "staff": "Has the radiology team reviewed your answers and confirmed you may continue?",
        "not_ready": "We cannot continue yet. Please wait for the radiology team.",
        "changing": "I will guide you to the changing room first.",
        "clothes": "Change into a hospital gown if staff asks you. Remove jewellery and metal objects only as instructed. Keep your belongings safe.",
        "prepared": "Have you finished preparing and received instructions from the radiology team?",
        "ct": "I will guide you to the CT room.",
        "lie": "Please lie on the CT table only when radiology staff tells you to. Follow their instructions and remain still.",
        "during": "During the scan, remain still and follow the team's breathing instructions. If you feel uncomfortable or unwell, tell staff immediately.",
        "complete": "Has the radiology team confirmed that your scan is complete?",
        "feeling": "Are you feeling well after your CT scan?",
        "well": "I am glad you feel well. Follow staff instructions before standing up. I will guide you to the waiting area.",
        "unwell": "Please remain seated or lying down and do not leave alone. I will alert the radiology team so they can assess you.",
        "waiting": "We have arrived at the waiting area.",
        "arrived": "We have arrived at the radiology team.",
        "finish": "Your guided journey has ended. Thank you.",
        "invalid": "Invalid choice. Please try again.",
        "yes_no": "1 = Yes, 2 = No",
        "movement": "Simulated robot movement...",
        "follow": "Please follow me to ",
        "arrive": "We have arrived at "
    },

    "de": {
        "welcome": "Hallo! Ich bin Ihr CT-Begleitroboter.",
        "questions": [
            "Hatten Sie jemals eine allergische Reaktion auf CT-Kontrastmittel?",
            "Haben Sie Nierenprobleme?",
            "Sind Sie schwanger oder könnten Sie schwanger sein?",
            "Haben Sie einen Herzschrittmacher, ein Implantat oder eine Medikamentenpumpe?",
            "Tragen Sie Schmuck, Piercings oder Metallgegenstände?",
            "Haben Sie herausnehmbaren Zahnersatz oder andere herausnehmbare Gegenstände?",
            "Gibt es Medikamente oder besondere Hinweise für das Radiologieteam?",
            "Haben Sie Angst vor der CT-Untersuchung?",
            "Benötigen Sie Hilfe beim Gehen oder beim Hinlegen auf den CT-Tisch?",
            "Benötigen Sie sprachliche oder kommunikative Unterstützung?"
        ],
        "screening": "Zuerst stelle ich Ihnen einige Sicherheitsfragen.",
        "answer": "Geben Sie 1 für Ja, 2 für Nein oder 3 für Unsicher ein:",
        "pause": "Wir müssen hier pausieren. Das Radiologieteam muss Ihre Antwort prüfen.",
        "staff": "Hat das Radiologieteam Ihre Antworten geprüft und bestätigt, dass Sie fortfahren dürfen?",
        "not_ready": "Wir können noch nicht fortfahren. Bitte warten Sie auf das Radiologieteam.",
        "changing": "Ich begleite Sie zuerst zur Umkleide.",
        "clothes": "Ziehen Sie einen Krankenhauskittel an, wenn das Personal Sie darum bittet. Entfernen Sie Schmuck und Metallgegenstände nur nach Anweisung. Bewahren Sie Ihre persönlichen Sachen sicher auf.",
        "prepared": "Sind Sie mit der Vorbereitung fertig und haben Sie Anweisungen vom Radiologieteam erhalten?",
        "ct": "Ich begleite Sie zum CT-Raum.",
        "lie": "Legen Sie sich erst auf den CT-Tisch, wenn das Personal Sie dazu auffordert. Befolgen Sie die Anweisungen und bleiben Sie still.",
        "during": "Bleiben Sie während der Untersuchung still und befolgen Sie die Atemanweisungen des Teams. Wenn Sie sich unwohl fühlen, informieren Sie das Personal sofort.",
        "complete": "Hat das Radiologieteam bestätigt, dass die Untersuchung abgeschlossen ist?",
        "feeling": "Fühlen Sie sich nach der CT-Untersuchung gut?",
        "well": "Schön, dass Sie sich gut fühlen. Befolgen Sie die Anweisungen, bevor Sie aufstehen. Ich begleite Sie zum Wartebereich.",
        "unwell": "Bleiben Sie bitte sitzen oder liegen und gehen Sie nicht allein weg. Ich informiere das Radiologieteam, damit es Sie untersuchen kann.",
        "waiting": "Wir sind im Wartebereich angekommen.",
        "arrived": "Wir sind beim Radiologieteam angekommen.",
        "finish": "Ihre begleitete Reise ist beendet. Vielen Dank.",
        "invalid": "Ungültige Auswahl. Bitte versuchen Sie es erneut.",
        "yes_no": "1 = Ja, 2 = Nein",
        "movement": "Simulierte Roboterbewegung...",
        "follow": "Bitte folgen Sie mir zu ",
        "arrive": "Wir sind angekommen: "
    }
}


# ==========================================
# BASIC FUNCTIONS
# ==========================================

def say(message):
    print("\nROBOT:", message)


def ask_yes_no(question, t):
    while True:
        print("\nROBOT:", question)
        print(t["yes_no"])
        answer = input("> ").strip()

        if answer == "1":
            return True
        elif answer == "2":
            return False
        else:
            say(t["invalid"])


def move_to(destination, t):
    say(t["follow"] + destination + ".")
    print(t["movement"])
    time.sleep(1)
    say(t["arrive"] + destination + ".")


# ==========================================
# SAFETY SCREENING
# ==========================================

def screening(t):
    say(t["screening"])

    for question in t["questions"]:
        while True:
            print("\nROBOT:", question)
            print(t["answer"])
            answer = input("> ").strip()

            if answer in ("1", "2", "3"):
                break

            say(t["invalid"])

        # Yes or Not sure: pause and refer to radiology staff.
        if answer in ("1", "3"):
            say(t["pause"])
            move_to("the radiology team" if t is TEXT["en"] else "dem Radiologieteam", t)
            say(t["arrived"])
            return False

    # Staff approval is required even when all answers are No.
    if not ask_yes_no(t["staff"], t):
        say(t["not_ready"])
        move_to("the radiology team" if t is TEXT["en"] else "dem Radiologieteam", t)
        return False

    return True


# ==========================================
# BEFORE THE CT SCAN
# ==========================================

def before_scan(t):
    print("\n===== BEFORE THE CT SCAN / VOR DER CT-UNTERSUCHUNG =====")

    say(t["changing"])
    move_to("the changing room" if t is TEXT["en"] else "der Umkleide", t)
    say(t["clothes"])

    if not ask_yes_no(t["prepared"], t):
        say(t["not_ready"])
        move_to("the radiology team" if t is TEXT["en"] else "dem Radiologieteam", t)
        return False

    say(t["ct"])
    move_to("the CT room" if t is TEXT["en"] else "dem CT-Raum", t)
    say(t["lie"])
    return True


# ==========================================
# DURING THE CT SCAN
# ==========================================

def during_scan(t):
    print("\n===== DURING THE CT SCAN / WÄHREND DER CT-UNTERSUCHUNG =====")

    say(t["during"])

    if not ask_yes_no(t["complete"], t):
        say(t["not_ready"])
        move_to("the radiology team" if t is TEXT["en"] else "dem Radiologieteam", t)
        return False

    return True


# ==========================================
# AFTER THE CT SCAN
# ==========================================

def after_scan(t):
    print("\n===== AFTER THE CT SCAN / NACH DER CT-UNTERSUCHUNG =====")

    if ask_yes_no(t["feeling"], t):
        say(t["well"])
        move_to("the waiting area" if t is TEXT["en"] else "dem Wartebereich", t)
        say(t["waiting"])
    else:
        say(t["unwell"])
        move_to("the radiology team" if t is TEXT["en"] else "dem Radiologieteam", t)
        say(t["arrived"])

    say(t["finish"])


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():
    print("====================================")
    print("   CT SCAN COMPANION / CT-BEGLEITER")
    print("====================================")
    print("1. English")
    print("2. Deutsch")

    while True:
        language = input("Choose language / Sprache wählen: ").strip()

        if language == "1":
            t = TEXT["en"]
            break
        elif language == "2":
            t = TEXT["de"]
            break
        else:
            print("Please enter 1 or 2 / Bitte geben Sie 1 oder 2 ein.")

    say(t["welcome"])

    if not screening(t):
        say(t["finish"])
        return

    if not before_scan(t):
        say(t["finish"])
        return

    if not during_scan(t):
        say(t["finish"])
        return

    after_scan(t)


if __name__ == "__main__":
    main()
