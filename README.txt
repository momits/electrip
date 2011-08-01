Lieber angehender Benutzer von ELECTRIP, im Folgenden die grundlegende Anleitung zur Installation und Benutzung.

Da das Programm bisher nur unter Linux getestet wurde, behandelt diese Anleitung nur die Installation auf einem Linux-System.
Allerdings sollte die Installation unter Windows oder Mac für Benutzer mit etwas Erfahrung kein Problem darstellen.

------INSTALLATION------
Installieren Sie den srcpd-server auf einem Rechner und richten Sie ihn für Ihre Bedürfnisse ein. Siehe dazu "https://sourceforge.net/projects/srcpd/".

1.	Laden Sie sich von http://electrip.svn.sourceforge.net/viewvc/electrip/ das *.tar.gz-Paket mit electrip herunter.
2.	Entpacken Sie den Ordner electrip an eine beliebige Stelle auf ihrer Festplatte.
3.	Im Verzeichnis ".../electrip/trunk/ELECTRIP_CONTROL" finden Sie die Datei "ELECTRIP_1.2.2HP.py". Markieren Sie die Datei als ausführbar.
	Verfahren Sie ebenso mit ".../electrip/trunk/ELECTRIP_CONFIGURATION/ELECTRIP_Configuration.py".
4. Im Ordner "ELECTRIP_CONFIGURATION" finden Sie außerdem die Datei conf.elc. Erstellen Sie im Verzeichnis "ELECTRIP_CONTROL" eine Verknüpfung auf diese Datei.
5. Ermitteln Sie, welche Adresse und welchen Port der srcpd-Server besitzt
6. Öffnen Sie die Datei "ELECTRIP_1.2.2HP.py" und tragen Sie diese Daten ganz unten ein:
--> Fenster("localhost", 4303, ....)
--> Ersetzen Sie "Localhost" durch die Adresse des Servers und 4303 durch den Port.
--> Das ist selbstverständlich nicht nötig, wenn Sie den Server mit dessen Standardeinstellungen lokal auf ihrem Rechner am Laufen haben!
6. Sie können loslegen!

------BENUTZUNG------
Steuern: ELECTRIP_1.2.2HP.py ausführen
Konfiguration ändern: ELECTRIP_Configuration.py ausführen

1. Zum Ändern der Lokparameter, bearbeiten Sie die Datei "conf.elc" mit dem Konfigurationseditor.
2. Den Namen im Dateifeld nicht verändern sondern bei "conf.elc" belassen (Die Möglichkeit verschiedene Konfigurationsdateien zu laden fehlt noch im Steuerprogramm.)
4. Hilfe zu den einzelnen Parametern finden Sie in der Legende.
5. Getestet wurde die Joysticksteuerung mit einem "Logitech RumblePad 2", sie ist noch nicht für alle Joystickmodelle ausgelegt. Ausprobieren!

------WAS IST NOCH ZU BEACHTEN?------
1. In dieser Version können noch keine beliebigen Dateien geladen werden, sondern nur die "conf.elc". Das wird sich bald ändern.
2. ELECTRIP ist noch ein sehr junges Projekt und wurde noch nicht wirklich getestet. Wenn Sie einen Fehler finden, melden Sie ihn!
