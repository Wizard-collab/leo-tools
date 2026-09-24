# -*- coding: utf-8 -*-
# Blender Deadline submitter for Deadline 10 (Windows)
# Local-only, no repository-side Blender submit script import.

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import bpy


bl_info = {
    "name": "Leo Deadline Blender Submitter",
    "description": "Submit the current Blender scene to Deadline without importing the repository Blender submission script",
    "author": "Leo Brunel",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Leo Tools > Deadline",
    "category": "Render",
}


DEFAULT_DEADLINE_PATHS = (
    r"C:\Program Files\Thinkbox\Deadline10\bin",
    r"C:\Program Files\Thinkbox\Deadline10\bin64",
    r"C:\Program Files\Thinkbox\Deadline\bin",
    r"C:\Program Files\Thinkbox\Deadline\bin64",
)

DEADLINE_ENUM_VALUES = {
    "plugin": ["4.5", "5.0"],
    "pool": ["none"],
    "group": ["none"],
}

SETTINGS_FIELDS = (
    "leo_deadline_ocio_path",
    "leo_deadline_blender_version",
    "leo_deadline_chunk_size",
    "leo_deadline_threads",
    "leo_deadline_build",
    "leo_deadline_pool",
    "leo_deadline_group",
    "leo_deadline_priority",
    "leo_deadline_machine_limit",
    "leo_deadline_comment",
    "leo_deadline_gpu_script",
)


def resolve_deadline_bin_path():
    """Find the Deadline bin directory.

    Priority order:
    1) DEADLINE_PATH
    2) DEADLINE_BIN
    3) common local install locations
    """
    candidates = []

    for env_name in ("DEADLINE_PATH", "DEADLINE_BIN"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(value)

    candidates.extend(DEFAULT_DEADLINE_PATHS)

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue

        cleaned = candidate.strip().strip('"').rstrip('\\/')
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)

        deadline_exe = os.path.join(cleaned, "deadlinecommand.exe")
        if os.path.isfile(deadline_exe):
            return os.path.dirname(deadline_exe)

        for possible_bin in (cleaned, os.path.join(cleaned, "bin"), os.path.join(cleaned, "bin64")):
            exe = os.path.join(possible_bin, "deadlinecommand.exe")
            if os.path.isfile(exe):
                return possible_bin

    return ""


def get_deadline_command():
    deadline_bin = resolve_deadline_bin_path()
    if not deadline_bin:
        raise RuntimeError(
            "Deadline could not be found. Set DEADLINE_PATH in the environment or install Deadline locally."
        )

    exe = os.path.join(deadline_bin, "deadlinecommand.exe")
    if not os.path.exists(exe):
        raise RuntimeError(
            "The Deadline command line executable was not found in: {0}".format(deadline_bin)
        )

    return exe


def normalize_windows_path(path):
    if not path:
        return path
    return path.replace("/", "\\")


def get_current_ocio_env_value():
    value = os.environ.get("OCIO")
    if value:
        return value.strip()
    return ""


def get_settings_file_path():
    config_dir = bpy.utils.user_resource("CONFIG")
    return os.path.join(config_dir, "leo_deadline_submitter_settings.json")


def load_submission_settings(scene):
    settings_path = get_settings_file_path()
    if not os.path.isfile(settings_path):
        return

    with open(settings_path, "r", encoding="utf-8") as handle:
        settings = json.load(handle)

    for field in SETTINGS_FIELDS:
        if field in settings:
            setattr(scene, field, settings[field])


def save_submission_settings(scene):
    settings_path = get_settings_file_path()
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    settings = {field: getattr(scene, field) for field in SETTINGS_FIELDS}
    with open(settings_path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=2, sort_keys=True)


def autofill_scene_submission_fields(scene):
    scene.leo_deadline_job_name = bpy.path.display_name(bpy.data.filepath) if bpy.data.filepath else scene.name
    scene.leo_deadline_output = scene.render.filepath
    scene.leo_deadline_frames = "{0}-{1}".format(scene.frame_start, scene.frame_end)

    ocio_value = get_current_ocio_env_value()
    if ocio_value:
        scene.leo_deadline_ocio_path = ocio_value


def sanitize_enum_identifier(value):
    text = str(value).strip()
    if not text:
        return "none"
    safe = re.sub(r"[^A-Za-z0-9_]", "_", text)
    safe = safe.strip("_") or "none"
    if safe[0].isdigit():
        safe = "v_" + safe
    return safe


def resolve_enum_identifier(value, available_values):
    if value in available_values:
        return value
    for candidate in available_values:
        if sanitize_enum_identifier(candidate) == value:
            return candidate
    return value


def deadline_enum_items(values, include_none=False):
    unique = []
    if include_none:
        unique.append("none")
    for value in values:
        item = str(value).strip()
        if not item or item.lower() in ("none", "null"):
            continue
        if item in unique:
            continue
        unique.append(item)

    return [(sanitize_enum_identifier(item), item, item) for item in unique]


def deadline_plugin_items(self, context):
    return deadline_enum_items(DEADLINE_ENUM_VALUES["plugin"], include_none=True)


def deadline_pool_items(self, context):
    return deadline_enum_items(DEADLINE_ENUM_VALUES["pool"], include_none=True)


def deadline_group_items(self, context):
    return deadline_enum_items(DEADLINE_ENUM_VALUES["group"], include_none=True)


def get_deadline_command_output(*args):
    try:
        deadline_exe = get_deadline_command()
    except Exception:
        return []

    command = [deadline_exe]
    command.extend(args)
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=False)
    except Exception:
        return []

    output = (result.stdout or "") + (result.stderr or "")
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_deadline_repository_file(relative_path):
    deadline_exe = get_deadline_command()
    result = subprocess.run(
        [deadline_exe, "-GetRepositoryPath", relative_path],
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode != 0:
        return ""

    paths = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return paths[-1] if paths else ""


def parse_deadline_list(raw_lines, fallback=()):
    values = []
    for line in raw_lines:
        cleaned = line.strip()
        if not cleaned:
            continue

        lower = cleaned.lower()
        if lower.startswith(("error", "warning")):
            continue
        if "bad submission arguments" in lower:
            continue
        if "unknown option" in lower or "unknown command" in lower:
            continue
        if "submission arguments" in lower and "bad" in lower:
            continue

        if "=" in cleaned:
            cleaned = cleaned.split("=", 1)[1].strip()
        if not cleaned:
            continue

        cleaned = cleaned.strip("[]()\"'")
        lower_candidate = cleaned.lower()
        if lower_candidate in ("none", "null"):
            continue
        if lower_candidate.startswith(("error", "warning")):
            continue
        if "bad submission arguments" in lower_candidate:
            continue

        if cleaned not in values:
            values.append(cleaned)

    if values:
        return values
    return list(fallback)


def parse_deadline_blender_plugin_values(raw_lines, fallback=("none",)):
    values = []
    for line in raw_lines:
        cleaned = line.strip()
        if not cleaned:
            continue

        lower = cleaned.lower()
        if lower.startswith(("error", "warning")):
            continue
        if "bad submission arguments" in lower:
            continue
        if "unknown option" in lower or "unknown command" in lower:
            continue
        if "submission arguments" in lower and "bad" in lower:
            continue

        if "=" in cleaned:
            cleaned = cleaned.split("=", 1)[1].strip()
        cleaned = cleaned.strip("[]()\"'")
        if not cleaned:
            continue

        cleaned = cleaned.replace("Blender ", "", 1).strip()
        if cleaned.lower().startswith("version "):
            cleaned = cleaned[7:].strip()

        if not cleaned:
            continue

        lower_candidate = cleaned.lower()
        if lower_candidate in ("none", "null"):
            continue
        if lower_candidate.startswith(("error", "warning")):
            continue
        if "bad submission arguments" in lower_candidate:
            continue

        if re.search(r"\d+(?:[._-]\d+)+", cleaned) or "blender" in lower_candidate:
            if cleaned not in values:
                values.append(cleaned)

    if values:
        return values
    return list(fallback)


def get_blender_versions_from_plugin_config():
    config_path = get_deadline_repository_file("plugins/Blender/Blender.param")
    if not config_path or not os.path.isfile(config_path):
        return []

    values = []
    in_executable_section = False
    with open(config_path, "r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line.startswith("[") and line.endswith("]"):
                in_executable_section = line == "[Blender_RenderExecutable]"
                continue
            if not in_executable_section or not line.startswith("Default="):
                continue

            executables = line.split("=", 1)[1].split(";")
            for executable in executables:
                match = re.search(r"(?:blender[ _-]?)?(\d+\.\d+(?:[._-][A-Za-z0-9]+)?)", executable, re.IGNORECASE)
                if match:
                    version = match.group(1)
                    if version not in values:
                        values.append(version)
    return values


def get_deadline_pool_values():
    candidates = [
        ["-GetPools"],
        ["-GetPoolNames"],
        ["-GetPoolInfo"],
    ]
    for args in candidates:
        lines = get_deadline_command_output(*args)
        values = parse_deadline_list(lines, fallback=("none",))
        if values and values != ["none"]:
            return values
    return ["none"]


def get_deadline_group_values():
    candidates = [
        ["-GetGroups"],
        ["-GetGroupNames"],
    ]
    for args in candidates:
        lines = get_deadline_command_output(*args)
        values = parse_deadline_list(lines, fallback=("none",))
        if values and values != ["none"]:
            return values
    return ["none"]


def looks_like_blender_plugin_value(value):
    text = str(value).strip()
    if not text:
        return False

    lower = text.lower()
    if lower in ("none", "null"):
        return False
    if any(marker in lower for marker in ("deadline command", "deadline", "thinkbox", "release")):
        return False
    if "blender" in lower:
        return True

    match = re.match(r"^(\d+)(?:[._-](\d+))?(?:[._-]([A-Za-z0-9]+))?$", text)
    if match:
        major = int(match.group(1))
        if 2 <= major <= 8:
            return True

    return False


def get_deadline_blender_plugin_values():
    values = get_blender_versions_from_plugin_config()
    filtered = []
    for value in values:
        if looks_like_blender_plugin_value(value) and value not in filtered:
            filtered.append(value)
    return filtered or ["none"]


def build_job_info_file(job_name, comment, frames, output_filename, chunk_size, pool, group, priority, machine_limit, ocio_path=""):
    temp_dir = tempfile.gettempdir()
    job_info_path = os.path.join(temp_dir, "blender_leo_job_info.job")

    with open(job_info_path, "w", encoding="utf-8", newline="") as handle:
        handle.write("Plugin=Blender\n")
        handle.write("Name={0}\n".format(job_name))
        handle.write("Comment={0}\n".format(comment))
        if pool and pool != "none":
            handle.write("Pool={0}\n".format(pool))
        if group and group != "none":
            handle.write("Group={0}\n".format(group))
        handle.write("Priority={0}\n".format(priority))
        handle.write("MachineLimit={0}\n".format(machine_limit))
        handle.write("Frames={0}\n".format(frames))
        handle.write("ChunkSize={0}\n".format(chunk_size))
        handle.write("TaskTimeoutMinutes=0\n")
        handle.write("ConcurrentTasks=1\n")
        handle.write("LimitConcurrentTasksToNumberOfCpus=True\n")
        handle.write("OnJobComplete=Nothing\n")
        handle.write("Department=\n")

        if ocio_path:
            handle.write("EnvironmentKeyValue0=OCIO={0}\n".format(ocio_path))

        if output_filename:
            handle.write("OutputFilename0={0}\n".format(output_filename))

    return job_info_path


def build_plugin_info_file(scene_path, output_filename, threads, build, gpu_script_path, blender_version):
    temp_dir = tempfile.gettempdir()
    plugin_info_path = os.path.join(temp_dir, "blender_leo_plugin_info.job")

    with open(plugin_info_path, "w", encoding="utf-8", newline="") as handle:
        handle.write("SceneFile={0}\n".format(scene_path))

        if output_filename:
            handle.write("OutputFile={0}\n".format(output_filename))

        handle.write("Threads={0}\n".format(threads))
        handle.write("Build={0}\n".format(build))
        if blender_version and blender_version != "none":
            handle.write("Version={0}\n".format(blender_version))

        additional_arguments = ""
        if gpu_script_path and os.path.exists(gpu_script_path):
            additional_arguments = gpu_script_path
        handle.write("AdditionalArguments={0}\n".format(additional_arguments))

    return plugin_info_path


def submit_to_deadline(scene_path, output_filename, frames, chunk_size, threads, build, pool, group, priority, machine_limit, gpu_script_path, job_name, comment, ocio_path="", blender_version="4_1"):
    if not scene_path or not os.path.exists(scene_path):
        raise FileNotFoundError("The Blender scene file does not exist: {0}".format(scene_path))

    deadline_exe = get_deadline_command()

    normalized_scene_path = normalize_windows_path(scene_path)
    normalized_output = normalize_windows_path(output_filename) if output_filename else ""
    normalized_gpu_script = normalize_windows_path(gpu_script_path) if gpu_script_path else ""

    job_info = build_job_info_file(
        job_name=job_name,
        comment=comment,
        frames=frames,
        output_filename=normalized_output,
        chunk_size=chunk_size,
        pool=pool,
        group=group,
        priority=priority,
        machine_limit=machine_limit,
        ocio_path=ocio_path,
    )
    plugin_info = build_plugin_info_file(
        scene_path=normalized_scene_path,
        output_filename=normalized_output,
        threads=threads,
        build=build,
        gpu_script_path=normalized_gpu_script,
        blender_version=blender_version,
    )

    with open(job_info, "r", encoding="utf-8") as handle:
        print("Deadline job info:\n{0}".format(handle.read()))
    with open(plugin_info, "r", encoding="utf-8") as handle:
        print("Deadline plugin info:\n{0}".format(handle.read()))

    cmd = [deadline_exe, job_info, plugin_info]

    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    output_text = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(output_text or "Deadline submission failed without error output.")

    return output_text.strip() or "Submission sent successfully."


class LEODeadlineSubmitOperator(bpy.types.Operator):
    bl_idname = "leo_tools.submit_blender_to_deadline"
    bl_label = "Submit To Deadline"
    bl_description = "Submit the current Blender scene to Deadline using a local submission flow"

    def invoke(self, context, event):
        if not bpy.data.filepath:
            self.report({"ERROR"}, "The Blender file must be saved before submitting.")
            return {"CANCELLED"}

        scene = context.scene
        try:
            DEADLINE_ENUM_VALUES["pool"] = get_deadline_pool_values()
            DEADLINE_ENUM_VALUES["group"] = get_deadline_group_values()
            load_submission_settings(scene)
            autofill_scene_submission_fields(scene)
        except Exception as exc:  # pragma: no cover - Blender UI error path
            self.report({"WARNING"}, "Could not load Deadline defaults: {0}".format(exc))

        return context.window_manager.invoke_props_dialog(self, width=520)

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "leo_deadline_job_name", text="Job name")
        layout.prop(scene, "leo_deadline_ocio_path", text="OCIO config")
        layout.prop(scene, "leo_deadline_blender_version", text="Blender plugin")
        layout.prop(scene, "leo_deadline_output", text="Output")
        layout.prop(scene, "leo_deadline_frames", text="Frames")
        layout.prop(scene, "leo_deadline_chunk_size", text="Frames per task")
        layout.prop(scene, "leo_deadline_threads", text="Threads")
        layout.prop(scene, "leo_deadline_build", text="Build")
        layout.prop(scene, "leo_deadline_pool", text="Pool")
        layout.prop(scene, "leo_deadline_group", text="Group")
        layout.prop(scene, "leo_deadline_priority", text="Priority")
        layout.prop(scene, "leo_deadline_machine_limit", text="Machine limit")
        layout.prop(scene, "leo_deadline_comment", text="Comment")
        layout.prop(scene, "leo_deadline_gpu_script", text="GPU script")

    def execute(self, context):
        scene = context.scene
        scene_path = bpy.data.filepath
        if not scene_path:
            self.report({"ERROR"}, "The Blender file must be saved before submitting.")
            return {"CANCELLED"}

        try:
            bpy.ops.wm.save_mainfile()
        except RuntimeError as exc:  # pragma: no cover - Blender UI error path
            self.report({"ERROR"}, "Could not save the Blender file: {0}".format(exc))
            return {"CANCELLED"}

        output_filename = scene.leo_deadline_output or scene.render.filepath
        frames = scene.leo_deadline_frames or "{0}-{1}".format(scene.frame_start, scene.frame_end)
        if not scene.leo_deadline_job_name:
            scene.leo_deadline_job_name = bpy.path.display_name(scene_path)
        job_name = scene.leo_deadline_job_name or bpy.path.display_name(scene_path)

        try:
            blender_plugin_value = resolve_enum_identifier(
                scene.leo_deadline_blender_version,
                DEADLINE_ENUM_VALUES["plugin"],
            )
            pool_value = resolve_enum_identifier(
                scene.leo_deadline_pool,
                DEADLINE_ENUM_VALUES["pool"],
            )
            group_value = resolve_enum_identifier(
                scene.leo_deadline_group,
                DEADLINE_ENUM_VALUES["group"],
            )
            result = submit_to_deadline(
                scene_path=scene_path,
                output_filename=output_filename,
                frames=frames,
                chunk_size=scene.leo_deadline_chunk_size,
                threads=scene.leo_deadline_threads,
                build=scene.leo_deadline_build,
                pool=pool_value,
                group=group_value,
                priority=scene.leo_deadline_priority,
                machine_limit=scene.leo_deadline_machine_limit,
                gpu_script_path=scene.leo_deadline_gpu_script,
                job_name=job_name,
                comment=scene.leo_deadline_comment,
                ocio_path=scene.leo_deadline_ocio_path,
                blender_version=blender_plugin_value,
            )
            save_submission_settings(scene)
            self.report({"INFO"}, result)
            return {"FINISHED"}

        except Exception as exc:  # pragma: no cover - Blender UI error path
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class LEODeadlineAutofillOperator(bpy.types.Operator):
    bl_idname = "leo_tools.deadline_autofill_from_scene"
    bl_label = "Autofill from Scene"
    bl_description = "Read the current scene render output path and frame range into the Deadline fields"

    def execute(self, context):
        scene = context.scene
        render_path = scene.render.filepath

        if not render_path:
            self.report({"WARNING"}, "The scene has no render output path set.")
            return {"CANCELLED"}

        scene.leo_deadline_output = render_path

        if not scene.leo_deadline_frames:
            scene.leo_deadline_frames = "{0}-{1}".format(scene.frame_start, scene.frame_end)

        if not scene.leo_deadline_job_name:
            scene.leo_deadline_job_name = bpy.path.display_name(bpy.data.filepath) if bpy.data.filepath else scene.name

        if not scene.leo_deadline_ocio_path:
            ocio_value = get_current_ocio_env_value()
            if ocio_value:
                scene.leo_deadline_ocio_path = ocio_value

        self.report({"INFO"}, "Deadline fields were autofilled from the scene.")
        return {"FINISHED"}


class LEODeadlineRefreshListsOperator(bpy.types.Operator):
    bl_idname = "leo_tools.deadline_refresh_lists"
    bl_label = "Refresh Deadline"
    bl_description = "Query Deadline for the current available plugin, pool, and group values"

    def execute(self, context):
        try:
            DEADLINE_ENUM_VALUES["pool"] = get_deadline_pool_values()
            DEADLINE_ENUM_VALUES["group"] = get_deadline_group_values()
            self.report({"INFO"}, "Deadline pool and group lists were refreshed.")
            return {"FINISHED"}
        except Exception as exc:  # pragma: no cover - Blender UI error path
            self.report({"ERROR"}, "Could not refresh Deadline data: {0}".format(exc))
            return {"CANCELLED"}


class LEODeadlinePanel(bpy.types.Panel):
    bl_label = "Deadline"
    bl_idname = "VIEW3D_PT_leo_deadline_submitter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Leo Tools"

    def draw(self, context):
        layout = self.layout
        layout.operator("leo_tools.submit_blender_to_deadline", text="Submit To Deadline")


classes = (
    LEODeadlineSubmitOperator,
    LEODeadlineAutofillOperator,
    LEODeadlineRefreshListsOperator,
    LEODeadlinePanel,
)


def register_properties():
    prop_names = (
        'leo_deadline_job_name',
        'leo_deadline_ocio_path',
        'leo_deadline_blender_version',
        'leo_deadline_output',
        'leo_deadline_frames',
        'leo_deadline_chunk_size',
        'leo_deadline_threads',
        'leo_deadline_build',
        'leo_deadline_pool',
        'leo_deadline_group',
        'leo_deadline_priority',
        'leo_deadline_machine_limit',
        'leo_deadline_comment',
        'leo_deadline_gpu_script',
    )

    for prop_name in prop_names:
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)

    bpy.types.Scene.leo_deadline_job_name = bpy.props.StringProperty(
        name="Job name",
        description="Custom name for the Deadline job",
        default="",
    )
    bpy.types.Scene.leo_deadline_ocio_path = bpy.props.StringProperty(
        name="OCIO config",
        description="Path to the OCIO config to inject as an environment variable in the Deadline job",
        subtype="FILE_PATH",
        default=get_current_ocio_env_value(),
    )
    bpy.types.Scene.leo_deadline_output = bpy.props.StringProperty(
        name="Output",
        description="Optional output filename override",
        subtype="FILE_PATH",
        default="",
    )
    bpy.types.Scene.leo_deadline_frames = bpy.props.StringProperty(
        name="Frames",
        description="Frame range to submit, for example 1-10 or 1-10,15",
        default="",
    )
    bpy.types.Scene.leo_deadline_chunk_size = bpy.props.IntProperty(
        name="Frames per task",
        description="Number of frames per Deadline task",
        default=1,
        min=1,
    )
    bpy.types.Scene.leo_deadline_threads = bpy.props.IntProperty(
        name="Threads",
        description="Threads to use for the Blender render",
        default=0,
        min=0,
        max=256,
    )
    bpy.types.Scene.leo_deadline_build = bpy.props.EnumProperty(
        name="Build",
        items=[
            ("None", "None", "Do not force a build"),
            ("32bit", "32bit", "Force 32-bit"),
            ("64bit", "64bit", "Force 64-bit"),
        ],
        default="None",
    )
    bpy.types.Scene.leo_deadline_blender_version = bpy.props.EnumProperty(
        name="Blender plugin",
        description="Blender plugin version available after refreshing Deadline",
        items=deadline_plugin_items,
    )
    bpy.types.Scene.leo_deadline_pool = bpy.props.EnumProperty(
        name="Pool",
        description="Deadline pool available after refreshing Deadline",
        items=deadline_pool_items,
    )
    bpy.types.Scene.leo_deadline_group = bpy.props.EnumProperty(
        name="Group",
        description="Deadline group available after refreshing Deadline",
        items=deadline_group_items,
    )
    bpy.types.Scene.leo_deadline_priority = bpy.props.IntProperty(
        name="Priority",
        description="Deadline priority",
        default=50,
        min=0,
        max=100,
    )
    bpy.types.Scene.leo_deadline_machine_limit = bpy.props.IntProperty(
        name="Machine limit",
        description="Machine limit for the job",
        default=0,
        min=0,
    )
    bpy.types.Scene.leo_deadline_comment = bpy.props.StringProperty(
        name="Comment",
        description="Job comment",
        default="",
    )
    bpy.types.Scene.leo_deadline_gpu_script = bpy.props.StringProperty(
        name="GPU script",
        description="Optional path to a BlenderForceGPU script",
        subtype="FILE_PATH",
        default="",
    )

def unregister_properties():
    for prop_name in (
        'leo_deadline_job_name',
        'leo_deadline_ocio_path',
        'leo_deadline_blender_version',
        'leo_deadline_output',
        'leo_deadline_frames',
        'leo_deadline_chunk_size',
        'leo_deadline_threads',
        'leo_deadline_build',
        'leo_deadline_pool',
        'leo_deadline_group',
        'leo_deadline_priority',
        'leo_deadline_machine_limit',
        'leo_deadline_comment',
        'leo_deadline_gpu_script',
    ):
        if hasattr(bpy.types.Scene, prop_name):
            delattr(bpy.types.Scene, prop_name)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    register_properties()


def unregister():
    unregister_properties()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
