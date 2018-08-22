# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

# See docs folder for detailed usage info.
import os
import sys
import sgtk
import shotgun_api3


def registerCallbacks(reg):
    """
    Register our callbacks.

    :param reg: A Registrar instance provided by the event loop handler.
    """

    # Grab authentication env vars for this plugin. Install these into the env
    # if they don't already exist.
    server = "https://ofg.shotgunstudio.com"
    script_name = "download_submission"
    script_key = "Fhhupdtir2nspoos&guxuraiq"

    # Grab an sg connection for the validator.
    sg = shotgun_api3.Shotgun(server, script_name=script_name, api_key=script_key)

    # Bail if our validator fails.
    if not is_valid(sg, reg.logger):
        reg.logger.warning("Plugin is not valid, will not register callback.")
        return

    eventFilter = {
        "Shotgun_Version_Change": ["sg_uploaded_movie"],
    }
    # Temp solution for remote artist
    args = {
        "applied_users": ["Allie Vanaman", "Yi Zheng"],
    }
    # Register our callback with the Shotgun_Version_Change event
    reg.registerCallback(
        script_name,
        script_key,
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
    user_name = event.get("user").get("name")
    if user_name not in args["applied_users"]:
        logger.debug("{} is not a remote artist.".format(user_name))
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
    logger.debug("version {}".format(version))


def get_tk(project):
    tk = sgtk.sgtk_from_path()

