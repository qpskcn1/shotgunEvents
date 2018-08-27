"""
Plugin to download all submissions of remote artists to local storage server

Author: Yi Zheng
Copyright 2018 OHIO FILM GROUP All rights reserved.
"""

import os
import sgtk
import shotgun_api3

# Grab authentication env vars for this plugin. Install these into the env
# if they don't already exist.
SERVER = os.environ["SG_SERVER"]
SCRIPT_NAME = os.environ["SGDAEMON_DOWNLOAD_NAME"]
SCRIPT_KEY = os.environ["SGDAEMON_DOWNLOAD_KEY"]


def registerCallbacks(reg):
    """
    Register our callbacks.

    :param reg: A Registrar instance provided by the event loop handler.
    """

    # Grab an sg connection for the validator.
    sg = shotgun_api3.Shotgun(SERVER, script_name=SCRIPT_NAME, api_key=SCRIPT_KEY)

    # Bail if our validator fails.
    if not is_valid(sg, reg.logger):
        reg.logger.warning("Plugin is not valid, will not register callback.")
        return

    eventFilter = {
        "Shotgun_Version_Change": ["sg_uploaded_movie"],
    }
    # Temp solution for remote artist
    args = {
        "applied_group": "Remote Artists",
    }
    # Register our callback with the Shotgun_Version_Change event
    reg.registerCallback(
        SCRIPT_NAME,
        SCRIPT_KEY,
        download_submission,
        eventFilter,
        args,
    )
    reg.logger.debug("Registered callback.")


def is_valid(sg, logger):
    """
    Validate our args.

    :param sg: Shotgun API handle.
    :param logger: Logger instance.
    :returns: True if plugin is valid, None if not.
    """

    # Make sure we have a valid sg connection.
    try:
        sg.find_one("Project", [])
        # sg.find_on("user", [])
    except Exception, e:
        logger.warning(e)
        return

    return True


def download_submission(sg, logger, event, args):
    """
    Assigns a HumanUser to a Project if that HumanUser is assigned to a Task
    which belongs to a Project s/he isn't already assigned to.

    :param sg: Shotgun API handle.
    :param logger: Logger instance.
    :param event: A Shotgun EventLogEntry entity dictionary.
    :param args: Any additional misc arguments passed through this plugin.
    """

    # Make some vars for convenience.
    event_project = event.get("project")
    # Bail if we don't have the info we need.
    if not event_project:
        return
    # Bail if artist is not in applied group
    user_id = event.get("user").get("id")
    groups = sg.find_one("HumanUser", [["id", "is", user_id]], ["groups"])["groups"]
    in_group = False
    for group in groups:
        if group["name"] == args["applied_group"]:
            in_group = True
    if not in_group:
        return
    # logger.info("%s" % str(event))
    event_meta = event.get("meta")
    entity_type = event_meta.get("entity_type")
    entity_id = event_meta.get("entity_id")
    # Re-query the Version to get necessary field values.
    version = sg.find_one(
        entity_type,
        [["id", "is", entity_id]],
        ["code", "entity", "sg_task", "user", "sg_uploaded_movie"]
    )
    # if entity or sg_task or sg_uploaded movie field is missing
    # do not download anything
    if not version["entity"] or \
       not version["sg_task"] or \
       not version["sg_uploaded_movie"]:
        logger.warning("File missing required field, cancel download!")
        return
    logger.debug("version {}".format(version))
    # get path for this version
    path = get_file_path(sg, event_project, version)
    sg.download_attachment(version["sg_uploaded_movie"], file_path=path)
    logger.info("File downloaded to {}".format(path))


def get_file_path(sg, project, version):
    # Use the authenticator to create a user object. This object
    # identifies a Shotgun user or script and also wraps around
    # a Shotgun API instance which is associated with that user
    sa = sgtk.authentication.ShotgunAuthenticator()
    script_user = sa.create_script_user(api_script=SCRIPT_NAME,
                                        api_key=SCRIPT_KEY,
                                        host=SERVER)
    sgtk.set_authenticated_user(script_user)
    # get toolkit manager
    mgr = sgtk.bootstrap.ToolkitManager(sg_user=script_user)
    mgr.plugin_id = "basic.*"
    project_id = project.get("id")
    engine = mgr.bootstrap_engine("tk-shell",
                                  entity={"type": "Project", "id": project_id})
    tk = engine.sgtk
    sg_asset_type = sg.find_one(
        "Asset",
        [["id", "is", version["entity"]["id"]]],
        ["sg_asset_type"]
    )["sg_asset_type"]
    step_id = sg.find_one(
        "Task",
        [["id", "is", version["sg_task"]["id"]]],
        ["step"]
    )["step"]["id"]
    step = sg.find_one(
        "Step",
        [["id", "is", step_id]],
        ["short_name"]
    )["short_name"]
    version_name = version["code"].split(".")
    name = version_name[0].split("_")[-1]
    version_number = version_name[1]
    if version_number.startswith("v"):
        version_number = version_number[1:]
    work_fields = {
        "Asset": version["entity"]["name"],
        "sg_asset_type": sg_asset_type,
        "Step": step,
        "name": name,
        "version": int(version_number),
    }
    ps_template = tk.templates["photoshop_asset_work"]
    path = ps_template.apply_fields(work_fields)
    engine.ensure_folder_exists(os.path.dirname(path))
    # destroy
    engine.destroy()
    return path
