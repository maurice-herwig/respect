# ReSpect User Study Design

## Ziel

Die User Study ergaenzt die automatisierte Evaluation auf oeffentlich
verfuegbaren GitHub-Spezifikationen. Sie untersucht explorativ, wie
Studierende Spectra-Spezifikationen aus natuerlichsprachlichen Anforderungen
rekonstruieren, wenn ihnen unterschiedliche Feedback- und Tooling-Level zur
Verfuegung stehen.

Der Fokus liegt auf zwei Beitraegen des Projekts:

- interaktive Skills zur strukturierten Spectra-Erstellung und Reparatur
- unabhaengige TestDSL-Vorschlaege plus Controller-Testfeedback

Die Studie ist wegen der kleinen Stichprobe als explorative Mixed-Methods-Study
zu interpretieren. Quantitative Ergebnisse werden deskriptiv berichtet und
durch Bildschirmaufnahmen, Artefaktlogs und kurze Frageboegen ergaenzt.

## Bedingungen

| Bedingung | Tooling | Zweck |
| --- | --- | --- |
| A | Eclipse/Spectra IDE plus allgemeine Modellierungscheckliste | Klassische manuelle Baseline |
| B | `respect-interactive-spec` ueber den Wizard | Interaktive skill-gestuetzte Spezifikation ohne Testfeedback |
| C | `respect-interactive-spec-tester` plus `respect-interactive-test-writer` ueber den Wizard | Interaktive skill-gestuetzte Spezifikation mit unabhaengigen TestDSL-Vorschlaegen und Testfeedback |

Der staerkste interne Vergleich ist B vs. C, weil beide Bedingungen denselben
Wizard und dieselbe Interaktionsform verwenden. A vs. B/C ist weiterhin
relevant, enthaelt aber zusaetzlich den Unterschied zwischen klassischer
IDE-Arbeit und Wizard-/Skill-gestuetzter Arbeit.

## Aufgaben

Es gibt 12 Aufgaben in drei Schwierigkeitsstufen:

| Schwierigkeit | Aufgaben |
| --- | --- |
| Easy | E1, E2, E3, E4 |
| Medium | M1, M2, M3, M4 |
| Hard | H1, H2, H3, H4 |

Jeder Studierende bearbeitet alle 12 Aufgaben:

- 4 Aufgaben in Bedingung A
- 4 Aufgaben in Bedingung B
- 4 Aufgaben in Bedingung C

Nach jeweils 4 Aufgaben wird eine Pause eingelegt.

## Wizard-Nutzung

Fuer Bedingung B und C starten die Studierenden:

```powershell
python experiments\user_study_wizard.py
```

Der Wizard fragt die Aufgabe ab. Falls vorbereitete Aufgaben unter
`user_study/tasks/*.txt` existieren, zeigt er sie als Menue. Falls keine
vorbereiteten Aufgaben existieren oder eine neue Aufgabe verwendet werden soll,
kann die natuerlichsprachliche Beschreibung direkt eingegeben werden. Die
Eingabe endet mit einer Zeile, die nur `END` enthaelt.

Danach fragt der Wizard, ob TestDSL-Unterstuetzung verwendet werden soll:

- `Nein`: Bedingung B, Skill ohne Tests
- `Ja`: Bedingung C, Spec-Skill plus separater TestDSL-Skill

Die Studierenden interagieren hauptsaechlich ueber Review-Dateien:

- `signature.reviewed.json`
- `decomposition.reviewed.md`
- `spec.reviewed.spectra`
- in Bedingung C zusaetzlich `tests/test-plan.reviewed.rtest`

Sie pruefen oder bearbeiten die Dateien und druecken danach im Terminal
`Enter`.

## Reihenfolge

Die folgende Tabelle verteilt Aufgaben und Bedingungen so, dass jeder
Studierende jede Aufgabe einmal bearbeitet und insgesamt vier Aufgaben pro
Bedingung hat. Die Reihenfolge ist rotiert, um Lern- und Ermuedungseffekte zu
reduzieren.

Legende:

- A = Eclipse/Spectra Baseline
- B = interaktiver Spec-Skill ohne Tests
- C = interaktiver Spec-Skill plus TestDSL/Testfeedback

| Reihenfolge | Student 1 | Student 2 | Student 3 | Student 4 |
| --- | --- | --- | --- | --- |
| 1 | E1 (A) | M2 (A) | H3 (B) | E2 (B) |
| 2 | M1 (B) | H2 (B) | E4 (A) | M2 (C) |
| 3 | H1 (C) | E3 (C) | M4 (B) | H2 (A) |
| 4 | E2 (B) | M3 (A) | H4 (C) | E3 (C) |
| Pause | Pause | Pause | Pause | Pause |
| 5 | M2 (C) | H3 (B) | E1 (A) | M3 (A) |
| 6 | H2 (A) | E4 (A) | M1 (B) | H3 (B) |
| 7 | E3 (C) | M4 (B) | H1 (C) | E4 (A) |
| 8 | M3 (A) | H4 (C) | E2 (B) | M4 (B) |
| Pause | Pause | Pause | Pause | Pause |
| 9 | H3 (B) | E1 (A) | M2 (C) | H4 (C) |
| 10 | E4 (A) | M1 (B) | H2 (A) | E1 (A) |
| 11 | M4 (B) | H1 (C) | E3 (C) | M1 (B) |
| 12 | H4 (C) | E2 (B) | M3 (A) | H1 (C) |

Hinweis: Da vier Studierende und drei Bedingungen kombiniert werden, kann jede
einzelne Aufgabe ueber alle Studierenden hinweg nicht perfekt gleich oft in
jeder Bedingung vorkommen. Die Tabelle sorgt aber dafuer, dass jede Person
balanciert ist und dass die Bedingungen ueber Reihenfolge und Schwierigkeit
gemischt auftreten.

## Datenerhebung

Fuer alle Bedingungen:

- Bildschirmaufnahme waehrend der Bearbeitung
- Start- und Endzeit pro Aufgabe
- finale `.spectra`-Datei
- Status: syntaktisch valide, realisierbar, synthetisiert
- kurze Likert-Fragen nach jeder Aufgabe

Zusaetzlich fuer B und C:

- Wizard-Artefakte in `experiments/user_study_runs/`
- Skill-Prompts und Skill-Ausgaben
- vorgeschlagene und reviewte Signature/Decomposition/Spec-Dateien
- `timeline.jsonl`
- `summary.json`

Zusaetzlich fuer C:

- vorgeschlagene, reviewte und finale `.rtest`-Dateien
- Test-Kompilierausgaben
- Controller-Testresultate
- Testfeedback-Reparaturen

## Likert-Fragen

Nach jeder Aufgabe sollten wenige kurze Fragen gestellt werden, z.B. mit einer
Skala von 1 bis 5:

```text
1 = stimme gar nicht zu
2 = stimme eher nicht zu
3 = teils/teils
4 = stimme eher zu
5 = stimme voll zu
```

Allgemeine Fragen fuer alle Bedingungen:

- Ich habe verstanden, warum meine Spezifikation korrekt oder fehlerhaft war.
- Das verfuegbare Feedback hat mir geholfen, die Spezifikation zu verbessern.
- Ich war sicher, welche Aenderungen ich uebernehmen sollte.
- Die Bearbeitung war kognitiv anstrengend.

Zusaetzliche Fragen fuer B und C:

- Ich konnte die Vorschlaege des Skills gut nachvollziehen.
- Ich konnte die Vorschlaege sinnvoll anpassen.

Zusaetzliche Fragen fuer C:

- Die TestDSL-Vorschlaege haben relevante Fehler sichtbar gemacht.
- Ich konnte gut beurteilen, ob ein Test gerechtfertigt oder zu stark war.
- Das Testfeedback half mir bei der Reparatur der Spezifikation.

Nach jedem Block von vier Aufgaben koennen zusaetzlich offene Fragen gestellt
werden:

- Was war in diesem Block am hilfreichsten?
- Was war verwirrend oder hinderlich?

## Auswertung

Quantitative/deskriptive Metriken:

- Erfolgsrate: parsebar, realisierbar, synthetisiert
- Zeit pro Aufgabe und Bedingung
- Anzahl Reparaturschleifen
- Anzahl manuell akzeptierter, geaenderter oder verworfener Vorschlaege
- in C: Anzahl erzeugter, geaenderter, geloeschter oder ergaenzter Tests
- in C: Anzahl Testfehler, die zu Spec-Reparaturen fuehren
- finale Qualitaet ueber bestehende Evaluationsskripte oder manuelle Rubric

Qualitative Daten:

- Bildschirmaufnahmen
- beobachtete Fehlersituationen
- Umgang mit Skill-Vorschlaegen
- Umgang mit TestDSL-Vorschlaegen
- subjektive Einschaetzung aus Likert- und offenen Fragen

## Schwachstellen Und Gegenmassnahmen

| Risiko | Gegenmassnahme |
| --- | --- |
| Kleine Stichprobe (`n=4`) | Studie als explorativ/mixed-methods berichten |
| Lerneffekte | Reihenfolge rotieren, Trainingsaufgabe vorab nicht auswerten |
| Carryover durch TestDSL | C nicht systematisch frueh oder spaet platzieren |
| A nutzt andere Umgebung als B/C | A als klassische IDE-Baseline ausweisen; Hauptvergleich B vs. C |
| Aufgaben-Schwierigkeit subjektiv | Aufgaben pro Bedingung und Person mischen; Schwierigkeit nachtraeglich ueber Zeit/Fehlerrate plausibilisieren |
| Studierende duerfen Vorschlaege frei anpassen | Vorschlaege und reviewed Dateien getrennt speichern |
| C erzeugt mehr Aufwand als B | Zeit und Qualitaet getrennt interpretieren |
| Bildschirmaufnahme beeinflusst Verhalten | Vorab erklaeren, dass Tooling und Workflow evaluiert werden, nicht die Person |
| LLM-Nondeterminismus | Skill-Versionen, Prompts, Outputs und Modellkonfiguration speichern |

## Pilot

Vor der eigentlichen Studie sollte ein Pilotlauf mit 2-3 Aufgaben durchgefuehrt
werden:

- eine Aufgabe in A
- eine Aufgabe in B
- eine Aufgabe in C

Der Pilot prueft, ob Aufgabenlaenge, Wizard-Texte, Review-Dateien, Logging,
Pausen und Zeitlimits praktikabel sind.
