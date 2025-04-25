from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json
from pathlib import Path
from settings import logger

@dataclass
class GenerationParameters:
    positive_prompt: str
    negative_prompt: Optional[str]
    width: int
    height: int
    steps: int
    cfg: float
    sampler: str
    noise_schedule: str
    smea: str
    seed: int
    model: str
    quality_toggle: bool
    undesired_content: str
    prompt_conversion: bool
    upscale: bool
    decrisper: bool
    variety_plus: bool
    vibe_transfer_used: bool = False # Added field to track if vibe transfer was used
    undesired_content_preset: Optional[str] = None # Added field for detected preset

@dataclass
class GenerationResult:
    success: bool
    error_message: Optional[str]
    database_message_id: Optional[int]
    attempts_made: int # Renamed from retry_count

@dataclass
class NAIGenerationHistory:
    generation_id: str
    timestamp: str  # ISO format string
    user_id: int
    generation_time: float
    parameters: GenerationParameters
    result: GenerationResult

    def to_dict(self) -> dict:
        return {
            "generation_id": self.generation_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "generation_time": self.generation_time,
            "parameters": vars(self.parameters),
            "result": {
                "success": self.result.success,
                "error_message": self.result.error_message,
                "database_message_id": self.result.database_message_id,
                "attempts_made": self.result.attempts_made # Use new field name
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NAIGenerationHistory':
        result_data = data.get("result", {})
        # Handle potential missing keys from older data and remove image_url
        result_data.setdefault("success", False)
        result_data.setdefault("error_message", None)
        result_data.setdefault("database_message_id", None)
        # Handle old 'retry_count' field for backward compatibility
        attempts_made = result_data.pop('retry_count', 0)
        result_data.setdefault("attempts_made", attempts_made)
        result_data.pop('image_url', None) # Remove image_url if it exists in old data

        # Handle potential missing undesired_content_preset and vibe_transfer_used in old data
        parameters_data = data.get("parameters", {})
        parameters_data.setdefault("undesired_content_preset", None)
        parameters_data.setdefault("vibe_transfer_used", False) # Ensure new field exists for old data


        return cls(
            generation_id=data["generation_id"],
            timestamp=data["timestamp"],
            user_id=data["user_id"],
            generation_time=data["generation_time"],
            parameters=GenerationParameters(**parameters_data),
            result=GenerationResult(**result_data)
        )

@dataclass
class NAIUserStats:
    user_id: int
    total_generations: int = 0
    successful_generations: int = 0
    failed_generations: int = 0
    total_generation_time: float = 0.0
    models_used: Dict[str, int] = field(default_factory=dict)
    samplers_used: Dict[str, int] = field(default_factory=dict)
    most_used_sizes: Dict[str, int] = field(default_factory=dict)
    average_steps: float = 0.0
    average_cfg: float = 0.0
    upscale_count: int = 0
    vibe_transfer_count: int = 0
    quality_toggle_count: int = 0 # Added field
    decrisper_count: int = 0 # Added field
    variety_plus_count: int = 0 # Added field
    director_tools_usage: Dict[str, int] = field(default_factory=dict)
    preset_usage: Dict[str, int] = field(default_factory=dict) # This will now store undesired_content_preset usage
    favorite_parameters: Dict[str, Any] = field(default_factory=dict)
    last_generation: Optional[str] = None  # ISO format string
    first_generation: Optional[str] = None  # ISO format string
    monthly_usage: Dict[str, int] = field(default_factory=dict)
    daily_usage: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "total_generations": self.total_generations,
            "successful_generations": self.successful_generations,
            "failed_generations": self.failed_generations,
            "total_generation_time": self.total_generation_time,
            "models_used": self.models_used,
            "samplers_used": self.samplers_used,
            "most_used_sizes": self.most_used_sizes,
            "average_steps": self.average_steps,
            "average_cfg": self.average_cfg,
            "upscale_count": self.upscale_count,
            "vibe_transfer_count": self.vibe_transfer_count,
            "quality_toggle_count": self.quality_toggle_count, # Include new field
            "decrisper_count": self.decrisper_count, # Include new field
            "variety_plus_count": self.variety_plus_count, # Include new field
            "director_tools_usage": self.director_tools_usage,
            "preset_usage": self.preset_usage,
            "favorite_parameters": self.favorite_parameters,
            "last_generation": self.last_generation,
            "first_generation": self.first_generation,
            "monthly_usage": self.monthly_usage,
            "daily_usage": self.daily_usage
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NAIUserStats':
        # Handle potential missing keys from older data
        data.setdefault("preset_usage", {}) # Ensure preset_usage exists
        data.setdefault("quality_toggle_count", 0) # Ensure new field exists for old data
        data.setdefault("decrisper_count", 0) # Ensure new field exists for old data
        data.setdefault("variety_plus_count", 0) # Ensure new field exists for old data
        return cls(**data)

    def update_with_generation(self, history: NAIGenerationHistory):
        """Update stats with a new generation"""
        try:
            # Basic stats
            self.total_generations += 1
            if history.result.success:
                self.successful_generations += 1
            else:
                self.failed_generations += 1

            self.total_generation_time += history.generation_time

            # Update model usage
            self.models_used[history.parameters.model] = self.models_used.get(history.parameters.model, 0) + 1

            # Update sampler usage
            self.samplers_used[history.parameters.sampler] = self.samplers_used.get(history.parameters.sampler, 0) + 1

            # Update size usage
            size_key = f"{history.parameters.width}x{history.parameters.height}"
            self.most_used_sizes[size_key] = self.most_used_sizes.get(size_key, 0) + 1

            # Update averages
            total_gens = self.successful_generations + self.failed_generations
            if total_gens > 0:
                self.average_steps = (self.average_steps * (total_gens - 1) + history.parameters.steps) / total_gens
                self.average_cfg = (self.average_cfg * (total_gens - 1) + history.parameters.cfg) / total_gens

            # Update special features usage
            if history.parameters.upscale:
                self.upscale_count += 1
            if history.parameters.vibe_transfer_used: # Check the new field
                self.vibe_transfer_count += 1
            if history.parameters.quality_toggle: # Update quality toggle count
                self.quality_toggle_count += 1
            if history.parameters.decrisper: # Update decrisper count
                self.decrisper_count += 1
            if history.parameters.variety_plus: # Update variety plus count
                self.variety_plus_count += 1
            # Track undesired content preset usage
            if history.parameters.undesired_content_preset:
                 self.preset_usage[history.parameters.undesired_content_preset] = self.preset_usage.get(history.parameters.undesired_content_preset, 0) + 1


            # Update timestamps
            current_time = history.timestamp
            if not self.first_generation:
                self.first_generation = current_time
            self.last_generation = current_time

            # Update time-based usage
            date = datetime.fromisoformat(current_time)
            month_key = date.strftime("%Y-%m")
            day_key = date.strftime("%Y-%m-%d")
            self.monthly_usage[month_key] = self.monthly_usage.get(month_key, 0) + 1
            self.daily_usage[day_key] = self.daily_usage.get(day_key, 0) + 1

        except Exception as e:
            logger.error(f"Error updating user stats: {str(e)}")

@dataclass
class NAIGlobalStats:
    total_generations: int = 0
    total_users: int = 0
    active_users_today: int = 0
    active_users_month: int = 0
    model_distribution: Dict[str, int] = field(default_factory=dict)
    sampler_distribution: Dict[str, int] = field(default_factory=dict)
    total_generation_time: float = 0.0
    average_parameters: Dict[str, float] = field(default_factory=lambda: {
        "steps": 0.0,
        "cfg": 0.0
    })
    peak_usage_times: Dict[str, int] = field(default_factory=dict)
    error_distribution: Dict[str, int] = field(default_factory=dict)
    upscale_ratio: float = 0.0
    vibe_transfer_ratio: float = 0.0
    quality_toggle_ratio: float = 0.0 # Added field
    decrisper_ratio: float = 0.0 # Added field
    variety_plus_ratio: float = 0.0 # Added field
    preset_distribution: Dict[str, int] = field(default_factory=dict) # Added for global preset distribution


    @property
    def average_generation_speed(self) -> float:
        """Calculate average generation speed (seconds per generation)"""
        if self.total_generations > 0:
            return self.total_generation_time / self.total_generations
        return 0.0

    def to_dict(self) -> dict:
        return {
            "total_generations": self.total_generations,
            "total_users": self.total_users,
            "active_users_today": self.active_users_today,
            "active_users_month": self.active_users_month,
            "model_distribution": self.model_distribution,
            "sampler_distribution": self.sampler_distribution,
            "average_parameters": self.average_parameters,
            "peak_usage_times": self.peak_usage_times,
            "error_distribution": self.error_distribution,
            "upscale_ratio": self.upscale_ratio,
            "vibe_transfer_ratio": self.vibe_transfer_ratio,
            "quality_toggle_ratio": self.quality_toggle_ratio, # Include new field
            "decrisper_ratio": self.decrisper_ratio, # Include new field
            "variety_plus_ratio": self.variety_plus_ratio, # Include new field
            "total_generation_time": self.total_generation_time,
            "average_generation_speed": self.average_generation_speed, # Include calculated property
            "preset_distribution": self.preset_distribution # Include preset distribution
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'NAIGlobalStats':
        # Handle potential missing keys from older data
        data.setdefault("total_generation_time", 0.0)
        data.setdefault("average_parameters", {"steps": 0.0, "cfg": 0.0})
        data.setdefault("peak_usage_times", {})
        data.setdefault("error_distribution", {})
        data.setdefault("upscale_ratio", 0.0)
        data.setdefault("vibe_transfer_ratio", 0.0)
        data.setdefault("quality_toggle_ratio", 0.0) # Ensure new field exists for old data
        data.setdefault("decrisper_ratio", 0.0) # Ensure new field exists for old data
        data.setdefault("variety_plus_ratio", 0.0) # Ensure new field exists for old data
        data.setdefault("preset_distribution", {}) # Ensure preset_distribution exists
        # Note: average_generation_speed is a property, not stored directly
        # Remove average_generation_speed from data before passing to __init__
        data.pop('average_generation_speed', None)
        return cls(**data)


    def update_with_generation(self, history: NAIGenerationHistory, user_stats: list):
        """Update global stats with a new generation"""
        try:
            self.total_generations += 1
            self.total_generation_time += history.generation_time

            # Update model distribution
            self.model_distribution[history.parameters.model] = self.model_distribution.get(history.parameters.model, 0) + 1

            # Update sampler distribution
            self.sampler_distribution[history.parameters.sampler] = self.sampler_distribution.get(history.parameters.sampler, 0) + 1

            # Update average parameters
            n = self.total_generations
            if n > 0:
                for param, value in [
                    ("steps", history.parameters.steps),
                    ("cfg", history.parameters.cfg)
                ]:
                    self.average_parameters[param] = (self.average_parameters[param] * (n - 1) + value) / n

            # Update time-based stats
            hour = datetime.fromisoformat(history.timestamp).strftime("%H")
            self.peak_usage_times[hour] = self.peak_usage_times.get(hour, 0) + 1

            # Update error distribution if failed
            if not history.result.success and history.result.error_message:
                self.error_distribution[history.result.error_message] = self.error_distribution.get(history.result.error_message, 0) + 1

            # Update user metrics
            self.total_users = len(set(u.user_id for u in user_stats))

            # Get today's and this month's active users
            today = datetime.now().strftime("%Y-%m-%d")
            this_month = datetime.now().strftime("%Y-%m")
            active_today = set()
            active_month = set()

            for user in user_stats:
                if today in user.daily_usage:
                    active_today.add(user.user_id)
                if this_month in user.monthly_usage:
                    active_month.add(user.user_id)

            self.active_users_today = len(active_today)
            self.active_users_month = len(active_month)

            # Update feature ratios (based on users who used the feature at least once)
            total_users_with_gens = len([u for u in user_stats if u.total_generations > 0])
            self.upscale_ratio = sum(1 for u in user_stats if u.upscale_count > 0) / total_users_with_gens if total_users_with_gens > 0 else 0
            self.vibe_transfer_ratio = sum(1 for u in user_stats if u.vibe_transfer_count > 0) / total_users_with_gens if total_users_with_gens > 0 else 0
            self.quality_toggle_ratio = sum(1 for u in user_stats if u.quality_toggle_count > 0) / total_users_with_gens if total_users_with_gens > 0 else 0 # Calculate ratio
            self.decrisper_ratio = sum(1 for u in user_stats if u.decrisper_count > 0) / total_users_with_gens if total_users_with_gens > 0 else 0 # Calculate ratio
            self.variety_plus_ratio = sum(1 for u in user_stats if u.variety_plus_count > 0) / total_users_with_gens if total_users_with_gens > 0 else 0 # Calculate ratio


            # Update global preset distribution
            if history.parameters.undesired_content_preset:
                 self.preset_distribution[history.parameters.undesired_content_preset] = self.preset_distribution.get(history.parameters.undesired_content_preset, 0) + 1


        except Exception as e:
            logger.error(f"Error updating global stats: {str(e)}")

class NAIStatsManager:
    def __init__(self, database_dir: Path):
        try:
            # Use the predefined directories from settings
            self.database_dir = settings.STATS_DIR
            self.history_file = settings.STATS_DIR / "nai_history.json"
            self.user_stats_file = settings.USER_STATS_DIR / "nai_user_stats.json"
            self.global_stats_file = settings.GLOBAL_STATS_DIR / "nai_global_stats.json"

            self.history: List[NAIGenerationHistory] = []
            self.user_stats: Dict[int, NAIUserStats] = {}
            self.global_stats = NAIGlobalStats()

            self.load_data()

            # Verify data integrity after loading
            issues = self.verify_stats_integrity()
            if any(issues.values()):
                logger.warning("Found issues during stats verification after load")
                for category, category_issues in issues.items():
                    if category_issues:
                        logger.warning(f"{category}: {len(category_issues)} issues found")

        except Exception as e:
            logger.error(f"Error initializing NAIStatsManager: {str(e)}")
            raise

    def load_data(self):
        """Load all data from files"""
        # Create all required directories and verify permissions
        for directory in [self.database_dir, settings.USER_STATS_DIR, settings.GLOBAL_STATS_DIR]:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                # Try to create a test file to verify write permissions
                test_file = directory / ".test_write"
                test_file.write_text("test")
                test_file.unlink()  # Remove test file
            except Exception as e:
                logger.error(f"Error with directory {directory}: {str(e)}")
                raise

        # Load history
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    file_content = f.read()
                    try:
                        data = json.loads(file_content)
                        # Explicitly remove 'image_url' from history data for backward compatibility
                        cleaned_history_data = []
                        for entry_data in data:
                            if 'result' in entry_data and 'image_url' in entry_data['result']:
                                del entry_data['result']['image_url']
                            cleaned_history_data.append(entry_data)
                        self.history = [NAIGenerationHistory.from_dict(h) for h in cleaned_history_data]
                    except json.JSONDecodeError as je:
                        logger.error(f"JSON decode error: {str(je)}")
                        logger.error(f"Invalid JSON at position {je.pos}")
                        raise
            else:
                logger.warning(f"History file {self.history_file} does not exist, starting fresh")
                self.history = []
        except Exception as e:
            logger.error(f"Error loading history data: {str(e)}")
            self.history = []

        # Load user stats
        try:
            if self.user_stats_file.exists():
                with open(self.user_stats_file, 'r') as f:
                    file_content = f.read()
                    try:
                        data = json.loads(file_content)
                        self.user_stats = {int(k): NAIUserStats.from_dict(v) for k, v in data.items()}
                    except json.JSONDecodeError as je:
                        logger.error(f"JSON decode error in user stats: {str(je)}")
                        logger.error(f"Invalid JSON at position {je.pos}")
                        raise
            else:
                logger.warning(f"User stats file {self.user_stats_file} does not exist, starting fresh")
                self.user_stats = {}
        except Exception as e:
            logger.error(f"Error loading user stats data: {str(e)}")
            self.user_stats = {}

        # Load global stats
        try:
            if self.global_stats_file.exists():
                with open(self.global_stats_file, 'r') as f:
                    file_content = f.read()
                    try:
                        data = json.loads(file_content)
                        self.global_stats = NAIGlobalStats.from_dict(data)
                    except json.JSONDecodeError as je:
                        logger.error(f"JSON decode error in global stats: {str(je)}")
                        logger.error(f"Invalid JSON at position {je.pos}")
                        raise
            else:
                logger.warning(f"Global stats file {self.global_stats_file} does not exist, starting fresh")
                self.global_stats = NAIGlobalStats()
        except Exception as e:
            logger.error(f"Error loading global stats data: {str(e)}")
            self.global_stats = NAIGlobalStats()

    def save_data(self):
        """Save all data to files"""
        try:
            # Ensure all directories exist
            self.database_dir.mkdir(parents=True, exist_ok=True)
            settings.USER_STATS_DIR.mkdir(parents=True, exist_ok=True)
            settings.GLOBAL_STATS_DIR.mkdir(parents=True, exist_ok=True)

            # Save history
            try:
                temp_history_file = self.history_file.with_suffix('.tmp')
                history_data = [h.to_dict() for h in self.history]
                with open(temp_history_file, 'w') as f:
                    json.dump(history_data, f, indent=2)
                temp_history_file.replace(self.history_file)
            except Exception as e:
                logger.error(f"Error saving history: {str(e)}")
                raise

            # Save user stats
            try:
                temp_user_stats_file = self.user_stats_file.with_suffix('.tmp')
                user_stats_data = {str(k): v.to_dict() for k, v in self.user_stats.items()}
                with open(temp_user_stats_file, 'w') as f:
                    json.dump(user_stats_data, f, indent=2)
                temp_user_stats_file.replace(self.user_stats_file)
            except Exception as e:
                logger.error(f"Error saving user stats: {str(e)}")
                raise

            # Save global stats
            try:
                temp_global_stats_file = self.global_stats_file.with_suffix('.tmp')
                global_stats_data = self.global_stats.to_dict()
                with open(temp_global_stats_file, 'w') as f:
                    json.dump(global_stats_data, f, indent=2)
                temp_global_stats_file.replace(self.global_stats_file)
            except Exception as e:
                logger.error(f"Error saving global stats: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Critical error saving stats data: {str(e)}")
            raise

    def add_generation(self, history: NAIGenerationHistory, overwrite: bool = False) -> bool:
        """Add a new generation to the stats.
           If overwrite is True and an entry with the same message ID exists, it will be replaced.
           Returns True if added/updated, False if skipped (only if overwrite is False and duplicate exists)."""
        try:
            # Check if a history entry with the same database_message_id already exists
            existing_entry_index = -1
            existing_history = None
            if history.result.database_message_id is not None:
                for i, entry in enumerate(self.history):
                    if entry.result.database_message_id == history.result.database_message_id:
                        existing_entry_index = i
                        existing_history = entry
                        break

            if existing_entry_index != -1:
                # Duplicate found
                if overwrite:
                    logger.info(f"Overwriting existing generation entry for message ID: {history.result.database_message_id}")

                    # --- Calculate and apply delta for overwrite ---
                    # This is a simplified delta calculation. A more robust one would
                    # need to handle all stat fields, including distributions and averages.
                    # For now, we'll focus on the most impactful ones and still rely
                    # on recalculation for full correctness on overwrite.
                    # TODO: Implement full delta calculation for overwrite

                    # For now, remove the old entry and add the new one, then recalculate.
                    # This is the current behavior but logged as a TODO for future improvement.
                    del self.history[existing_entry_index]
                    self.history.append(history)
                    self._recalculate_stats() # Still recalculate on overwrite
                    logger.warning("Overwrite performed, but full delta calculation is not yet implemented. Recalculating stats.")
                    # --- End of simplified delta calculation ---

                    return True
                else:
                    # Duplicate found, but overwrite is False - skip
                    logger.warning(f"Skipping duplicate generation entry for message ID: {history.result.database_message_id}")
                    return False
            else:
                # No duplicate found - NEW entry
                self.history.append(history)

                # Apply incremental updates to user stats
                if history.user_id not in self.user_stats:
                    self.user_stats[history.user_id] = NAIUserStats(user_id=history.user_id)
                user_stats = self.user_stats[history.user_id]
                user_stats.update_with_generation(history)

                # Apply incremental updates to global stats
                # Note: Global stats update needs the list of user stats for active user calculation.
                # Passing list(self.user_stats.values()) might be inefficient for many users,
                # but it's still better than recalculating from the entire history.
                self.global_stats.update_with_generation(history, list(self.user_stats.values()))

                # DO NOT call self._recalculate_stats() here for new entries.

                return True # Indicate that the generation was added successfully

        except Exception as e:
            logger.error(f"Error adding/updating generation: {str(e)}")
            return False # Indicate failure

    def _recalculate_stats(self):
        """Recalculate user and global stats from the current history."""
        #logger.info("Recalculating user and global stats from history...")
        # Reset stats
        self.user_stats = {}
        self.global_stats = NAIGlobalStats()

        # Sort history by timestamp to ensure correct chronological updates
        sorted_history = sorted(self.history, key=lambda x: datetime.fromisoformat(x.timestamp))

        # Replay history to rebuild stats
        for history_entry in sorted_history:
            # Update user stats
            if history_entry.user_id not in self.user_stats:
                self.user_stats[history_entry.user_id] = NAIUserStats(user_id=history_entry.user_id)
            self.user_stats[history_entry.user_id].update_with_generation(history_entry)

            # Update global stats (pass current user_stats list for active user calculation)
            self.global_stats.update_with_generation(history_entry, list(self.user_stats.values()))

        #logger.info("Stats recalculation complete.")


    def get_user_stats(self, user_id: int) -> Optional[NAIUserStats]:
        """Get stats for a specific user"""
        stats = self.user_stats.get(user_id)
        return stats

    def get_global_stats(self) -> NAIGlobalStats:
        """Get global statistics"""
        return self.global_stats

    def get_user_history(self, user_id: int, limit: int = 10) -> List[NAIGenerationHistory]:
        """Get generation history for a specific user"""
        user_history = [h for h in self.history if h.user_id == user_id]
        sorted_history = sorted(user_history, key=lambda x: x.timestamp, reverse=True)[:limit]
        return sorted_history

    def verify_stats_integrity(self) -> Dict[str, List[str]]:
        """Verify the integrity of stats data and find any inconsistencies"""
        issues = {
            "history": [],
            "user_stats": [],
            "global_stats": [],
            "cross_reference": []
        }

        # Check history entries
        for i, entry in enumerate(self.history):
            try:
                # Verify timestamp format
                datetime.fromisoformat(entry.timestamp)
            except ValueError:
                issues["history"].append(f"Invalid timestamp format in history entry {i}: {entry.timestamp}")

            # Verify user exists in user_stats
            if entry.user_id not in self.user_stats:
                issues["cross_reference"].append(f"History entry {i} references non-existent user {entry.user_id}")

        # Check user stats
        for user_id, stats in self.user_stats.items():
            # Check for impossible values
            if stats.successful_generations + stats.failed_generations != stats.total_generations:
                issues["user_stats"].append(f"User {user_id} has inconsistent generation counts")

            if stats.total_generations > 0:
                if not stats.first_generation or not stats.last_generation:
                    issues["user_stats"].append(f"User {user_id} missing generation timestamps")
                try:
                    if stats.first_generation:
                        datetime.fromisoformat(stats.first_generation)
                    if stats.last_generation:
                        datetime.fromisoformat(stats.last_generation)
                except ValueError as e:
                    issues["user_stats"].append(f"User {user_id} has invalid timestamp format: {str(e)}")

        # Check global stats
        if self.global_stats.total_generations < 0:
            issues["global_stats"].append("Negative total generations count")

        total_user_generations = sum(user.total_generations for user in self.user_stats.values())
        if total_user_generations != self.global_stats.total_generations:
            issues["cross_reference"].append(
                f"Global generations count ({self.global_stats.total_generations}) "
                f"doesn't match sum of user generations ({total_user_generations})"
            )

        if self.global_stats.total_users != len(self.user_stats):
            issues["cross_reference"].append(
                f"Global user count ({self.global_stats.total_users}) "
                f"doesn't match actual user count ({len(self.user_stats)})"
            )

        # Log findings
        for category, category_issues in issues.items():
            if category_issues:
                logger.warning(f"Found {len(category_issues)} issues in {category}")
                for issue in category_issues:
                    logger.warning(f"- {issue}")

        return issues

try:
    import settings
    logger.info("Settings imported successfully for stats manager")
except Exception as e:
    logger.error(f"Error importing settings: {str(e)}")
    raise

# Create stats manager instance
try:
    stats_manager = NAIStatsManager(settings.STATS_DIR)
    logger.info("Stats manager initialized successfully")
except Exception as e:
    logger.error(f"Error creating stats manager: {str(e)}")
    raise
