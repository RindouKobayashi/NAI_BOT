import discord
import json
import os
import settings # Assuming settings.py is in the parent directory or accessible
from discord.ext import commands

# File paths (relative to the bot's root directory)
VERSION_FILE = "version.txt"
CHANGELOG_FILE = "changelog.md"
NOTIFIED_USERS_FILE = "database/notified_users.json"

async def notify_user_of_update(interaction: discord.Interaction):
    """
    Checks if a user needs to be notified about a bot update and sends a changelog message in the channel.
    Notification occurs only once per user per bot version.
    """
    user_id = str(interaction.user.id)

    try:
        # Ensure the notified_users.json file exists with default content if not found
        if not os.path.exists(NOTIFIED_USERS_FILE):
            os.makedirs(os.path.dirname(NOTIFIED_USERS_FILE), exist_ok=True)
            with open(NOTIFIED_USERS_FILE, "w") as f:
                json.dump({}, f)
            settings.logger.info(f"Created default notified users file: {NOTIFIED_USERS_FILE}")

        # 1. Get current bot version
        # Access version from bot instance attributes loaded in main.py
        current_version = getattr(interaction.client, 'current_version', 'Unknown')
        changelog_content = getattr(interaction.client, 'changelog_content', 'Changelog not loaded.')
        notified_users_data = getattr(interaction.client, 'notified_users_data', {})

        if current_version == "Unknown":
            settings.logger.warning("Bot version not loaded. Cannot check for updates.")
            return True # Allow command to proceed

        # Check if the user has already been notified for this version
        # The structure will be { "version": [user_id1, user_id2, ...], ... }
        notified_for_version = notified_users_data.get(current_version, [])

        if user_id in notified_for_version:
            # User already notified for this version, do nothing
            return True # Allow command to proceed

        # 3. Load changelog content (already loaded in main.py, access from bot instance)
        # changelog_content = ... accessed from bot instance

        # --- Start: Logic to extract last 2-3 changes (latest versions) ---
        # Assuming version changes are delineated by lines starting with '## ' (markdown level 2 headings)
        changelog_lines = changelog_content.splitlines()
        version_section_start_indices = []
        for i, line in enumerate(changelog_lines):
            # Assuming version sections start with '## '
            if line.strip().startswith('## '):
                version_section_start_indices.append(i)

        # Determine how many sections to include (e.g., last 3 latest versions)
        num_sections_to_include = 3 # Can be adjusted
        start_index_for_latest_changes = 0 # Default to start of file
        end_index_for_latest_changes = len(changelog_lines) # Default to end of file

        if len(version_section_start_indices) > 0: # Ensure there's at least one version section
             # The latest versions are at the beginning of the list of indices
             # Get the index of the start of the first version section to include
             start_index_for_latest_changes = version_section_start_indices[0]

             # Determine the index where the content should end
             # This is the start of the section *after* the num_sections_to_include-th section
             if len(version_section_start_indices) > num_sections_to_include:
                 end_index_for_latest_changes = version_section_start_indices[num_sections_to_include]
             # If there are fewer than num_sections_to_include sections, the end index is the end of the file (already set)


        # Extract the lines for the latest changes
        latest_changes_lines = changelog_lines[start_index_for_latest_changes:end_index_for_latest_changes]
        latest_changes_content = "\n".join(latest_changes_lines)
        # --- End: Logic to extract last 2-3 changes (latest versions) ---

        # 4. Notify the user by sending a message in the channel
        try:
            max_discord_length = 2000
            markdown_overhead = len("```markdown\n") + len("\n```\n-# This message will self-delete in 1 minute.") # 14 + 45 = 59

            header = f"🚀 Update for {interaction.client.user.name} (Version {current_version})!\n"
            if len(header) > max_discord_length - markdown_overhead: # Check if header alone is too long
                 header = "🚀 Bot Updated!\n" # Fallback

            current_chunk_content = ""
            is_first_chunk = True

            # --- Modify this loop to use last_changes_content instead of changelog_content ---
            # for line in changelog_content.splitlines(): # Original line
            # --- Modify this loop to use latest_changes_content instead of last_changes_content ---
            # for line in changelog_content.splitlines(): # Original line
            # for line in last_changes_content.splitlines(): # Previous modified line
            for line in latest_changes_content.splitlines(): # Modified line
            # --- End modification ---
            # --- End modification ---
                line_to_add = line + "\n"
                # Calculate potential length if this line is added
                potential_chunk_length = len(current_chunk_content) + len(line_to_add)

                # Calculate total message length if this chunk is sent now
                total_message_length_if_sent = markdown_overhead + potential_chunk_length
                if is_first_chunk:
                    total_message_length_if_sent += len(header)

                # Check if adding this line would exceed the limit
                if total_message_length_if_sent > max_discord_length:
                    # Send the current chunk
                    message_to_send = f"```markdown\n{current_chunk_content}\n```\n-# This message will self-delete in 1 minute."
                    if is_first_chunk:
                        message_to_send = header + message_to_send
                        is_first_chunk = False # Mark first chunk as sent

                    await interaction.channel.send(message_to_send, allowed_mentions=discord.AllowedMentions.none(), delete_after=60)

                    # Start a new chunk with the current line
                    current_chunk_content = line_to_add
                else:
                    # Add the line to the current chunk
                    current_chunk_content += line_to_add

            # Send the last chunk if it's not empty
            if current_chunk_content:
                message_to_send = f"```markdown\n{current_chunk_content}\n```\n-# This message will self-delete in 1 minute."
                if is_first_chunk: # This handles the case where the entire changelog fits in one chunk
                    message_to_send = header + message_to_send

                await interaction.channel.send(message_to_send, allowed_mentions=discord.AllowedMentions.none(), delete_after=60)

        except discord.Forbidden:
            settings.logger.warning(f"Could not send update notification message to channel {interaction.channel.id} (Missing permissions).")
            # If sending fails, don't mark as notified
            return True # Allow command to proceed
        except Exception as e:
            settings.logger.error(f"Error sending update notification message to channel {interaction.channel.id}: {e}")
            # If sending fails, don't mark as notified
            return True # Allow command to proceed


        # 5. Mark user as notified for this version and save
        notified_for_version.append(user_id)
        notified_users_data[current_version] = notified_for_version

        try:
            # Ensure directory exists before writing
            os.makedirs(os.path.dirname(NOTIFIED_USERS_FILE), exist_ok=True)
            with open(NOTIFIED_USERS_FILE, "w") as f:
                json.dump(notified_users_data, f, indent=4)
            # Update the bot instance's data as well
            setattr(interaction.client, 'notified_users_data', notified_users_data)
        except Exception as e:
            settings.logger.error(f"Error saving notified users data to {NOTIFIED_USERS_FILE}: {e}")
            return True
        
        return True # Allow command to proceed

    except Exception as e:
        # Catch any unexpected errors in the main logic
        settings.logger.error(f"An unexpected error occurred in update notification logic for user {user_id}: {e}")
        return True
