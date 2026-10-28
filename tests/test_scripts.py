"""
The six scripts on Persian input, plus English golden values that must not
move. The English numbers are the ones published in the README.

Run from the repo root, standard library only:

    python -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
for folder in ("ig-human", "ig-reel", "ig-caption", "ig-viral"):
    sys.path.insert(0, os.path.join(SKILLS, folder))

import beats      # noqa: E402
import caption    # noqa: E402
import detect     # noqa: E402
import hookscore  # noqa: E402
import humanize   # noqa: E402
import swipe      # noqa: E402

Z = "‌"
LEX = humanize.load_lexicon()

FA_DRAFT = (
    f"من می{Z}خواهم با هوش مصنوعی ۱۸ میلیون تومان صرفه{Z}جویی کنم. "
    f"این کار ۵ ساعت طول می{Z}کشید. حالا ۲۰ دقیقه است! "
    f"شما هم می{Z}توانید؛ فقط کافی است امروز شروع کنید. "
    f"«پرامپت» را کپی کنید و نتیجه را برای من بفرستید، چون می{Z}خواهم بدانم "
    f"در کار شما چه تغییری داد و چقدر وقت آزاد کرد."
)


class Humanize(unittest.TestCase):
    def test_keeps_every_half_space(self):
        clean, report = humanize.humanize(FA_DRAFT, LEX)
        self.assertEqual(clean.count(Z), FA_DRAFT.count(Z))
        self.assertEqual(report["invisible"], [])

    def test_em_dash_becomes_the_persian_comma(self):
        clean, _ = humanize.humanize("این روش — اگر درست اجرا شود — جواب می‌دهد.", LEX)
        self.assertEqual(clean.strip(), "این روش، اگر درست اجرا شود، جواب می‌دهد.")

    def test_em_dash_is_still_a_latin_comma_in_english(self):
        clean, _ = humanize.humanize("It works — if you ship it.", LEX)
        self.assertEqual(clean.strip(), "It works, if you ship it.")

    def test_fixes_the_missing_half_space(self):
        clean, report = humanize.humanize("من می خواهم مدل ها را مقایسه کنم.", LEX)
        self.assertEqual(clean.strip(), f"من می{Z}خواهم مدل{Z}ها را مقایسه کنم.")
        self.assertTrue(report["persian"])

    def test_still_strips_a_zero_width_space(self):
        clean, report = humanize.humanize("می​خواهم یاد بگیرم", LEX)
        self.assertNotIn("​", clean)
        self.assertEqual(report["invisible"][0]["count"], 1)

    def test_still_strips_a_half_space_hidden_in_english(self):
        clean, _ = humanize.humanize(f"Con{Z}tent is king.", LEX)
        self.assertEqual(clean.strip(), "Content is king.")

    def test_replaces_persian_cliches(self):
        clean, report = humanize.humanize("در دنیای امروز، هوش مصنوعی نقش کلیدی دارد.", LEX)
        self.assertEqual(clean.strip(), "هوش مصنوعی نقش اصلی دارد.")
        self.assertEqual({h["family"] for h in report["lexical"]}, {"fa-openers", "fa-filler"})

    def test_deleted_opener_mid_text_leaves_no_comma(self):
        clean, _ = humanize.humanize("این مهم است. در دنیای امروز، هر کسی پرامپت می‌نویسد.", LEX)
        self.assertEqual(clean.strip(), "این مهم است. هر کسی پرامپت می‌نویسد.")

    def test_cliche_found_with_half_space_or_space(self):
        for text in (f"می{Z}توان گفت که این بهترین مدل است.", "می توان گفت که این بهترین مدل است."):
            clean, _ = humanize.humanize(text, LEX)
            self.assertEqual(clean.strip(), "این بهترین مدل است.", text)

    def test_flags_persian_structures(self):
        _, report = humanize.humanize("این فقط یک ابزار نیست، یک دستیار کامل است.", LEX)
        self.assertIn("«این فقط X نیست، Y است»", [h["name"] for h in report["structures"]])


class Detect(unittest.TestCase):
    def test_correct_persian_is_not_a_fingerprint(self):
        results, _, verdict = detect.run(FA_DRAFT, LEX)
        self.assertEqual(results["FINGERPRINT"][0], 100.0)
        self.assertNotEqual(verdict, "FLAGGED")

    def test_all_five_run_on_persian(self):
        results, _, _ = detect.run(FA_DRAFT, LEX)
        self.assertTrue(all(results[c][0] is not None for c in detect.CHECKS))

    def test_persian_slop_lowers_the_score(self):
        sloppy = ("در دنیای امروز هوش مصنوعی نقش کلیدی دارد و لازم به ذکر است که "
                  "این ابزار شگفت‌انگیز به طور چشمگیری کار ما را متحول می‌کند. "
                  "بدون شک آینده اینجاست و انتخاب با شماست. همانطور که می‌دانید "
                  "این امر از اهمیت ویژه‌ای برخوردار است.")
        clean_score = detect.run(FA_DRAFT, LEX)[0]["SLOP DENSITY"][0]
        slop_score, detail = detect.run(sloppy, LEX)[0]["SLOP DENSITY"]
        self.assertEqual(clean_score, 100.0)
        self.assertLess(slop_score, 30)
        self.assertIn("stock terms", detail)

    def test_persian_voice_counts_structures_not_pronouns(self):
        flat = FA_DRAFT + " این فقط یک ابزار نیست، یک دستیار است. نه تنها سریع است بلکه دقیق است."
        plain = detect.run(FA_DRAFT, LEX)[0]["VOICE"]
        tells = detect.run(flat, LEX)[0]["VOICE"]
        self.assertEqual(plain[0], 100.0)
        self.assertLess(tells[0], plain[0])
        self.assertIn("fa-not-just", tells[1])

    def test_persian_voice_counts_each_kind_of_tell_once(self):
        # Five emoji bullets in a human-written caption are one habit.
        bullets = FA_DRAFT + "\n" + "\n".join(f"✅ نکته‌ی شماره {i} برای ساخت ریلز" for i in range(5))
        self.assertEqual(detect.run(bullets, LEX)[0]["VOICE"][0], 78.0)

    def test_persian_words_are_counted(self):
        self.assertGreater(len(detect.words(FA_DRAFT)), 25)

    def test_english_still_runs_all_five(self):
        results, _, _ = detect.run("I wrote this myself and I'm proud of it. " * 8, LEX)
        self.assertTrue(all(results[c][0] is not None for c in detect.CHECKS))


class HookScore(unittest.TestCase):
    def test_english_scores_match_the_readme(self):
        for hook, score, verdict in [
            ("Nobody tells you that your first 30 reels are supposed to flop", 85.6, "STRONG"),
            ("I lost $18,000 because of one missing contract.", 81.4, "STRONG"),
            ("Stop scrolling if you want to grow on Instagram in 2026 🔥", 54.4, "OK"),
            ("Hey guys, today I wanted to talk about content strategy", 9.6, "WEAK"),
        ]:
            _, overall, v, _ = hookscore.run(hook)
            self.assertEqual((round(overall, 1), v), (score, verdict), hook)

    def test_persian_hook_length_is_measured_in_seconds(self):
        # Ten Persian words take about 5.2 s at 115 wpm, past the 4.4 s an
        # English hook gets, so a ten-word Persian hook is long.
        results, _, _, _ = hookscore.run("۱۸ میلیون تومان را به‌خاطر یک قرارداد از دست دادم.")
        self.assertIn("10 words", results["LENGTH"][1])
        self.assertIn("want 4-8 words", results["LENGTH"][1])
        self.assertEqual(round(results["LENGTH"][0], 1), 74.2)
        results, _, _, _ = hookscore.run("۱۸ میلیون تومان سر یک قرارداد باختم.")
        self.assertEqual(results["LENGTH"][0], 100.0)

    def test_persian_runs_all_five(self):
        results, _, _, _ = hookscore.run("۱۸ میلیون تومان را به‌خاطر یک قرارداد از دست دادم.")
        self.assertEqual(hookscore.scored(results), 5)

    def test_persian_matches_english_on_the_same_hooks(self):
        # The README's English pair, said in Persian, should land where the
        # English did: both strong, and the greeting at the bottom.
        for hook, verdict in [
            ("هیچ‌کس بهت نمی‌گه که ۳۰ تا ریلز اولت قراره شکست بخوره.", "STRONG"),
            ("۱۸ میلیون تومان را به‌خاطر یک قرارداد از دست دادم.", "STRONG"),
            ("سلام بچه‌ها، امروز می‌خوام درباره‌ی استراتژی محتوا صحبت کنم", "WEAK"),
        ]:
            self.assertEqual(hookscore.run(hook)[2], verdict, hook)

    def test_persian_stakes_and_address(self):
        results, _, _, flags = hookscore.run("هیچ‌وقت این پرامپت رو بدون تست نفرستید.")
        self.assertGreaterEqual(results["STAKES"][0], 70)
        self.assertEqual(results["ADDRESS"][0], 90.0)            # imperative, at the end
        self.assertEqual(flags, [])

    def test_persian_dealbreakers(self):
        _, _, _, flags = hookscore.run("در این ویدیو قراره بهتون نشون بدم چطور کار کنید")
        self.assertIn("Video preamble. Delete it and open on the payoff.", flags)

    def test_negated_past_verb_is_at_stake(self):
        results, _, _, _ = hookscore.run("این موشن رو من نساختم")
        self.assertEqual(results["STAKES"][0], 70.0)

    def test_tu_meaning_in_is_not_you(self):
        results, _, _, _ = hookscore.run("تو این ریلز سه ابزار هوش مصنوعی رو مقایسه کردم.")
        self.assertEqual(results["ADDRESS"][0], 70.0)            # first person, not "you"


class Beats(unittest.TestCase):
    SCRIPT = ("۱۸ میلیون تومان را به‌خاطر یک قرارداد از دست دادم.\n"
              "این بند را الان در همه قراردادهایم می‌گذارم.\n"
              "پرداخت هنگام تحویل، نه هنگام تأیید.\n"
              "همین یک بند ۱۸ میلیون تومان برای من ارزش داشت.")

    def test_persian_script_has_a_length(self):
        a = beats.analyse(self.SCRIPT)
        self.assertEqual(a["total_words"], 34)          # 10 + 8 + 6 + 10
        self.assertGreater(a["total_seconds"], 0)

    def test_loop_found_and_stopwords_ignored(self):
        notes = " ".join(beats.analyse(self.SCRIPT)["notes"])
        self.assertIn("Loops:", notes)
        self.assertNotIn("را", notes.split("Loops:")[1].split("from the hook")[0])

    def test_persian_uses_the_measured_rate_unless_given(self):
        a = beats.analyse(self.SCRIPT)
        self.assertEqual(a["wpm"], 115)
        self.assertAlmostEqual(a["total_seconds"], 34 / 115 * 60, places=1)
        self.assertIn("measured on one Persian reel", " ".join(a["notes"]))
        b = beats.analyse(self.SCRIPT, wpm=150)
        self.assertEqual(b["wpm"], 150)
        self.assertNotIn("measured on one Persian reel", " ".join(b["notes"]))

    def test_english_timing_unchanged(self):
        a = beats.analyse("I lost $18,000 because of one missing contract.\n"
                          "That one word change is worth $18,000 to me.")
        self.assertEqual(a["total_words"], 17)          # 8 + 9, "$18,000" is one
        self.assertNotIn("English speaking rate", " ".join(a["notes"]))


class Caption(unittest.TestCase):
    def test_persian_hashtags_count_against_the_cap(self):
        text = ("یک بند در قرارداد ۱۸ میلیون تومان برایم هزینه داشت.\n\n"
                "#هوش_مصنوعی #آموزش #پرامپت #چت‌جی‌پی‌تی #فریلنسر #قرارداد")
        a = caption.analyse(text)
        self.assertEqual(len(a["hashtags"]), 6)
        self.assertIn("#چت‌جی‌پی‌تی", a["hashtags"])
        status = {c["check"]: c["status"] for c in a["checks"]}
        self.assertEqual(status["HASHTAGS"], "FAIL")

    def test_persian_ask_is_counted(self):
        a = caption.analyse("کلمه پرامپت را کامنت کنید تا برایتان بفرستم.")
        status = {c["check"]: c["status"] for c in a["checks"]}
        self.assertEqual(a["asks"], ["comment a keyword"])
        self.assertEqual(status["ONE ASK"], "PASS")

    def test_two_persian_asks_warn(self):
        a = caption.analyse(f"این پست رو سیو کن و پیجمو فالو کن تا آموزش بعدی رو از دست ندی.")
        status = {c["check"]: c["status"] for c in a["checks"]}
        self.assertEqual(sorted(a["asks"]), ["follow", "save this"])
        self.assertEqual(status["ONE ASK"], "WARN")

    # The next three came from real captions of a Persian AI-education page.

    def test_share_with_a_whole_clause_before_the_verb(self):
        a = caption.analyse("برای رفیقت که تولید محتوا می‌کنه بفرست.")
        self.assertEqual(a["asks"], ["share this"])
        a = caption.analyse("این پست را برای همکارهایتان بفرستید.")
        self.assertEqual(a["asks"], ["share this"])

    def test_a_bare_domain_is_a_dead_link(self):
        a = caption.analyse("لینکشو بردار و از ssspin.io دانلودش کن.\n🌐 yoursite.ir")
        self.assertEqual(a["links"], ["ssspin.io", "yoursite.ir"])

    def test_five_tags_is_not_a_wall(self):
        five = "یک متن.\n#موشن_گرافیک #هوش_مصنوعی #کلود #تولید_محتوا #ادیت_ویدیو"
        _, report = humanize.humanize(five, LEX)
        self.assertNotIn("hashtag-wall", str(report["structures"]))
        _, report = humanize.humanize(five + " #ریلز", LEX)
        self.assertIn("Hashtag wall (6+)", [h["name"] for h in report["structures"]])

    def test_persian_filler_tags(self):
        a = caption.analyse("سه ابزار رایگان برای ساخت کاروسل.\n\n#هوش_مصنوعی #اکسپلور #فالو")
        status = {c["check"]: c["status"] for c in a["checks"]}
        self.assertEqual(status["HASHTAGS"], "WARN")
        self.assertIn("#اکسپلور", [c["detail"] for c in a["checks"]
                                   if c["check"] == "HASHTAGS"][0])

    def test_search_term_found_however_it_is_typed(self):
        a = caption.analyse("این آموزش هوش‌مصنوعي برای مبتدی‌هاست.", keywords=["هوش مصنوعی"])
        status = {c["check"]: c["status"] for c in a["checks"]}
        self.assertEqual(status["SEARCH TERMS"], "PASS")


class Swipe(unittest.TestCase):
    def test_persian_rows_and_digits(self):
        import tempfile
        rows = ("account\tfollowers\tmedian\tviews\thook\n"
                "@fa_ai\t۹۰۰۰\t۳۰۰۰\t۱۸۰۰۰۰\tاین پرامپت را بدزدید، دو سال طول کشید\n")
        with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(rows)
        try:
            parsed = swipe.read_rows(fh.name)
        finally:
            os.unlink(fh.name)
        a = swipe.analyse(parsed, swipe.load_formulas(swipe.HOOKS))
        reel = a["reels"][0]
        self.assertEqual(reel["outlier"], 60.0)
        self.assertEqual(reel["words"], 8)
        self.assertEqual(reel["formula"], "The Steal")

    def test_every_persian_example_names_its_own_formula(self):
        formulas = swipe.load_formulas(swipe.HOOKS)
        with open(swipe.HOOKS, encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        for h in hooks:
            self.assertEqual(swipe.classify(h["example_fa"], formulas)[0], h["id"], h["name"])

    def test_plain_persian_sentences_stay_unclassified(self):
        formulas = swipe.load_formulas(swipe.HOOKS)
        for s in ["هوش مصنوعی یک ابزار مفید برای تولید محتوا است",
                  "امروز درباره‌ی پرامپت‌نویسی صحبت می‌کنیم",
                  "کلاس‌های آنلاین ما از شنبه شروع می‌شود"]:
            self.assertEqual(swipe.classify(s, formulas), (None, "unclassified"), s)

    def test_english_examples_unchanged(self):
        # The English path ignores match_fa entirely.
        formulas = swipe.load_formulas(swipe.HOOKS)
        self.assertEqual(swipe.classify("Steal this four-line follow-up.", formulas)[1], "The Steal")


class WindowsConsole(unittest.TestCase):
    """Persian through stdin and stdout, with no -X utf8 and no PYTHONUTF8.
    On Windows this used to come back as mojibake."""

    def test_stdin_round_trip(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
        p = subprocess.run(
            [sys.executable, "-B", os.path.join(SKILLS, "ig-human", "humanize.py"), "-", "--json"],
            input=FA_DRAFT.encode("utf-8"), capture_output=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        out = json.loads(p.stdout.decode("utf-8"))
        self.assertEqual(out["text"].strip(), FA_DRAFT)


if __name__ == "__main__":
    unittest.main()
