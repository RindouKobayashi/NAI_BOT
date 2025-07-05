# Changelog

## 1.1.7 - 2025-07-05
### Added
- Added `streaming` option to `nai` command (only works for v4 and above).
- A timelapse of the generation process will be shown if the `streaming` option is enabled.
- Generation time will be longer if the `streaming` option is enabled. (Due to how discord handles message editing)

## 1.1.6 - 2025-06-02
### Added
- Added `nai-diffusion-4-5-full` model (Nai v4.5 support).

## 1.1.5 - 2025-05-16
### Added
- Implemented a system to notify users about bot updates with the changelog, ensuring each user is notified only once per version.

## 1.1.4 - 2025-05-06
### Added
- Adds support for `nai-diffusion-4-5-curated` model (Nai v4.5 support).
### Changed
- Updates the default tag list for the `nai-diffusion-4-5-curated` model
to prepend `very aesthetic,` to quality tags as per changelog from Anlatan.

## 1.1.3 - 2025-04-25
### Added
- Introducing `vibe_transfer_preset`! You can now save and load your favorite configurations for the `vibe_transfer` command using presets.

### Important
- We've identified potentially corrupted data for the `vibe_transfer` feature for the following users. This issue may have been present for some time, but due to limited usage, it might not have been noticeable. **Unfortunately, there is no automated fix for this corrupted data.**
- Affected User IDs:
> `310707162634649601`
> `700480750344077373`
> `1039354321663430717`
> `520167794998902785`
> `360422025812246531`
> `106077589323390976`
> `757723198522654790`
> `444257402007846942`
> `467127086776188930`
> `878337390584950795`
- **If you are one of the users listed above and wish to use the `vibe_transfer` feature, you will need to re-add your vibe transfer data.** We apologize for any inconvenience this may cause.

## 1.1.2 - 2025-04-25
### Fixed
- The quality_toggle functionality has been addressed. It should now properly respect user settings.

### Added
- A Leaderboard has been implemented. Users can choose whether or not their name is displayed on it.
- Stats Tracking has been introduced.

## 1.1.1 - 2025-03-08
### Added
- Allow saving of presets for quick and easy generation (NAI preset supports).

## 1.1.0 - 2025-03-01
### Added
- Added nai-diffusion-4-full model (Nai v4 support).
- The default generation model is still v3 model. If frequent users request for v4 to be default, I can make the change.

## 1.0.13 - 2024-10-16
### Fixed
- Previously, using remix button, people can actually toggle `upscale` to `True` and it will ignore width and height limit, costing anlas in the generation process.

## 1.0.12 - 2024-10-09
### Added
- Added a forward button to <#1280389884745482313> generation. Message will be forwarded to <#1261084844230705182>, image will be deleted from original message. For the accidental nsfw that got thru the filters, but not bad enough that you want to trash it.

## 1.0.11 - 2024-10-05
### Added
- Added context menu for getting tags of image. Right click message containing image > `Apps` > `Get tags using wd-tagger` to get an embed of said image with tags using wd-tagger. This can be used on images without metadata.

## 1.0.10 - 2024-10-05
### Changed
- Buttons timeout been changed from 120 seconds to 600 seconds.
- Known issue: if button isn't timeout while bot went down, it will never timeout. But the button will not do anything even when pressed.

## 1.0.9 - 2024-10-04
### Changed
- Nai command will only be allowed on whitelisted server, like this one. You can request for whitelist by contacting me, or using /feedback command.
- Reason: because people were using nai command on server with NAI staff.

## 1.0.8 - 2024-10-03
### Added
- Right click message containing images > `Apps` > `Classify image` to get a classification using wd-tagger. This should give you the confidence levels and how it is classified using some "smol logic" with the confidence levels. Do note that the classification might be highly incorrect but it's how nai-chan classify image before deciding if image should be forwarded to #🐧│nsfw-image-gen-bot.

## 1.0.7 - 2024-09-24
### Added
- New option for nai command `variety_plus`, enable guidance only after body been formed, improved diversity, saturation of samples. (default: False).
- thanks to <@396774290588041228> for the code

## 1.0.6 - 2024-09-07
### Added
- New sampler > DPM++ 2M SDE

### Changed
- Edit sampler: ddim > ddim_v3
- Noise_schedule can now be chosen, default to "native"

## 1.0.5 - 2024-08-21
### Changed
- Updated director_tools to support upto 1024x1024

### Added
- Added decrisper (basically dynamic thresholding) to NAI command

### Fixed
- Auto-retrying should only be once, but currently it's twice.

## 1.0.4 - 2024-08-19
### Added
- Added director_tools command for image up to 832x1216. Remove background is not available via this bot.

### Fixed
- Auto-retrying should only be once, but currently it's twice.

## 1.0.3 - 2024-08-17
### Added
- Added remix button, you can now edit "most" stuff after you generated. Should be pretty self explanatory. The undesired content presets is kinda buggy on that, so use with care.
- Remix button can be used by other people, button will timeout in 120 seconds. Button pressing refreshes the timeout timer.

### Fixed
- Quality_toggle is now working as intended, appending or prepending depending on the model. (default = True) As such, old generations on this bot might need quality_toggle = false to get same image.
- SMEA is finally working as intended.
- If there's any bugs, please do let me know thru /feedback command

## 1.0.2 - 2024-08-13
### Added
- New feature: reSeed button for easy "spamming" of reseeding, it should be available for 120 seconds. And anyone can press that button on your generation as well.
- ps: if using vibe transfer, you will still use your own

## 1.0.1 - 2024-07-13
### Added
- `quality_toggle` default = `True`
- `undesired_content_presets` default = `Heavy`
- Conversation of auto1111 kinds of weighting bracket to NAI kinds has been turned off by default. Use `prompt_conversion_toggle` to `true` for auto conversion
- Trash button
 - Author reacting with 🗑️ should delete generation
 - Reaction count of 🗑️ is more than 2 (exlusive of bot reaction)

## 1.0.0 - 2024-07-12
Initial release.
