# Text Diff and Merge Tool

Dieses Repository enthält ein kleines Python-Programm, das zwei Textdateien
vergleicht, die Unterschiede visuell hervorhebt und bei der Zusammenführung
unterstützt. Das Programm nutzt ausschließlich Bibliotheken der Python
-Standardbibliothek und funktioniert daher auf aktuellen Windows- und macOS-
Systemen (sowie Linux), sobald Python 3 installiert ist.

## Voraussetzungen

* Python 3.8 oder neuer mit installiertem `tkinter` (gehört bei vielen
  Standard-Installationen bereits dazu).

## Starten der Anwendung

```bash
python text_diff_merge.py
```

Anschließend öffnet sich ein Fenster mit drei Bereichen:

1. **Left Document** – Inhalt der linken Datei.
2. **Right Document** – Inhalt der rechten Datei.
3. **Merged Result** – Bereich, in den Sie die gewünschten Textblöcke
   übernehmen.

## Bedienung

1. Klicken Sie auf **Load Left** bzw. **Load Right**, um die Dateien zu laden.
   Alternativ können Sie Text direkt in die Felder einfügen.
2. Mit **Compare** werden die Unterschiede analysiert und farbig markiert.
3. Mit **Previous Difference** und **Next Difference** navigieren Sie durch die
   gefundenen Unterschiede.
4. Verwenden Sie **Use Left**, **Use Right** oder **Copy Both**, um den jeweils
   markierten Unterschied in den Bereich *Merged Result* zu übernehmen.
5. **Clear Merge** leert den Merge-Bereich, **Save Merge** speichert das Ergebnis
   in eine Datei.

## Hinweise

* Unterschiede im linken Text werden rosafarben, im rechten hellblau
  hervorgehoben. Gemeinsame Ersetzungen erscheinen beige, die aktuell
  ausgewählte Differenz gelb.
* Die Anwendung arbeitet zeilenbasiert.
* Für sehr große Dateien kann der Vergleich einige Zeit in Anspruch nehmen.
