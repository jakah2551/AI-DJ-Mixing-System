# AI DJ Pipeline Runner
"""Run the complete AI DJ pipeline with optional progress callbacks."""

import os
import logging
from dotenv import load_dotenv

from track_analysis_openai_approach import combined_engine
from bpm_lookup import process_bpm_lookup
from structure_detector import process_structure_detection
from generate_mixing_plan import generate_mixing_plan
from mixing_engine import generate_mix

load_dotenv()
SONGS_DIR = "./songs"
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AI_DJ_Pipeline')
logging.getLogger('numba').setLevel(logging.WARNING)


def run_pipeline(user_input: str, progress_callback=None):
    """Execute all five stages.

    ``progress_callback`` is optional and receives ``(percent, stage, message)``.
    Existing command-line callers remain fully compatible.
    """
    def progress(percent, stage, message):
        if progress_callback:
            progress_callback(percent, stage, message)
        logger.info(message)

    try:
        progress(5, "selection", "Selecting tracks with AI…")
        combined_engine(user_input, output_path=os.path.join(OUTPUT_DIR, "analyzed_setlist.json"))
        if not os.path.exists(os.path.join(OUTPUT_DIR, "analyzed_setlist.json")):
            raise FileNotFoundError("analyzed_setlist.json not created.")

        progress(25, "analysis", "Analyzing BPM, key, genre and energy…")
        process_bpm_lookup(
            os.path.join(OUTPUT_DIR, "analyzed_setlist.json"),
            os.path.join(OUTPUT_DIR, "basic_setlist.json"),
        )
        if not os.path.exists(os.path.join(OUTPUT_DIR, "basic_setlist.json")):
            raise FileNotFoundError("basic_setlist.json not created.")

        progress(45, "structure", "Detecting choruses, vocals and transition points…")
        process_structure_detection(
            os.path.join(OUTPUT_DIR, "basic_setlist.json"),
            os.path.join(OUTPUT_DIR, "structure_data.json"),
        )
        if not os.path.exists(os.path.join(OUTPUT_DIR, "structure_data.json")):
            raise FileNotFoundError("structure_data.json not created.")

        progress(65, "planning", "Building harmonic and phrase-aware mixing plan…")
        generate_mixing_plan(
            basic_setlist_path=os.path.join(OUTPUT_DIR, "basic_setlist.json"),
            structure_json_path=os.path.join(OUTPUT_DIR, "structure_data.json"),
            output_path=os.path.join(OUTPUT_DIR, "mixing_plan.json"),
        )
        if not os.path.exists(os.path.join(OUTPUT_DIR, "mixing_plan.json")):
            raise FileNotFoundError("mixing_plan.json not created.")

        progress(80, "mixing", "Rendering the final DJ mix…")
        generate_mix(
            mixing_plan_json=os.path.join(OUTPUT_DIR, "mixing_plan.json"),
            structure_json=os.path.join(OUTPUT_DIR, "structure_data.json"),
            output_path=os.path.join(OUTPUT_DIR, "mix.mp3"),
        )
        if not os.path.exists(os.path.join(OUTPUT_DIR, "mix.mp3")):
            raise FileNotFoundError("mix.mp3 not created.")

        progress(100, "complete", "Mix generated successfully.")
        return os.path.join(OUTPUT_DIR, "mix.mp3")
    except Exception as e:
        logger.error(f"Pipeline execution failed: {str(e)}")
        if progress_callback:
            progress_callback(0, "error", f"Generation failed: {e}")
        raise


if __name__ == "__main__":
    run_pipeline("Mix all songs")
