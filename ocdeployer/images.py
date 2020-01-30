import logging

from sh import ErrorReturnCode

from .utils import oc, validate_list_of_strs


log = logging.getLogger("ocdeployer.images")


def _parse_config(config):
    images = []

    for img in config.get("images", []):
        if not isinstance(img, dict):
            raise ValueError("entries in 'images' must be of type 'dict'")
        if len(img.keys()) >= 2 and all([k in img for k in ["istag", "from"]]):
            # This entry is using new-style image definition, e.g.
            #   images:
            #   - istag: "image_name"
            #   - from: "quay.io/some/image_name:image_tag"
            #   - envs: ["stage", "prod"]
            istag = img["istag"]
            _from = img["from"]
            envs = img.get("envs", [])
        elif len(img.keys()) == 1 and all([k not in img for k in ["istag", "from", "envs"]]):
            # This entry is using old-style image definition, e.g.
            #   images:
            #   - "image_name:image_tag": "quay.io/some/image_name:image_tag"
            istag, _from = list(img.items())[0]
            envs = []
        else:
            raise ValueError("Unknown syntax for 'images' section of config")

        if not isinstance(istag, str) or not isinstance(_from, str):
            raise ValueError("'istag' and 'from' must be a of type 'string'")
        validate_list_of_strs("envs", "images", envs)

        images.append({"istag": istag, "from": _from, "envs": envs})

    return images


def _retag_image(istag, image_from):
    istag_split = istag.split(":")
    image_name = istag_split[0]
    if len(istag_split) < 2:
        image_tag = "latest"
    else:
        image_tag = istag_split[1:]

    oc(
        "tag", "--scheduled=True", "--source=docker", image_from, f"{image_name}:{image_tag}",
    )


def import_images(config, env_names):
    """Import the specified images listed in a _cfg.yml"""
    images = _parse_config(config)
    for img_data in images:
        istag = img_data["istag"]
        image_from = img_data["from"]
        if not img_data["envs"] or any([e in env_names for e in img_data["envs"]]):
            try:
                oc(
                    "import-image",
                    istag,
                    "--from={}".format(image_from),
                    "--confirm",
                    "--scheduled=True",
                    _reraise=True,
                )
            except ErrorReturnCode as err:
                if "use the 'tag' command if you want to change the source" in str(err.stderr):
                    _retag_image(istag, image_from)
        else:
            log.info("Skipping import of image '%s', not enabled for this env", img_data["istag"])