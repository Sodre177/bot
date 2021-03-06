import logging
import discord.utils
import util.db.kv
import util.discord
import plugins.commands

logger = logging.getLogger(__name__)
conf = util.db.kv.Config(__name__)

def has_privilege(priv, user_or_member):
    obj = conf[priv]
    if obj and "users" in obj:
        if user_or_member.id in obj["users"]:
            return True
    if obj and "roles" in obj:
        if hasattr(user_or_member, "roles"):
            for role in user_or_member.roles:
                if role.id in obj["roles"]:
                    return True
        # else we're in a DM or the user has left,
        # either way there's no roles to check
    return False

def priv(name):
    """
    Require that a command is only available to a given privilege. The decorator
    should be specified after plugins.commands.command.
    """
    def decorator(fun):
        async def check(msg, arg):
            if has_privilege(name, msg.author):
                await fun(msg, arg)
            else:
                logger.warn(
                    "Denied {} to {!r}".format(fun.__name__, msg.author))
        return check
    return decorator

def user_id_from_arg(guild, arg):
    if isinstance(arg, plugins.commands.UserMentionArg):
        return arg.id
    if not isinstance(arg, plugins.commands.StringArg): return None
    user = util.discord.smart_find(arg.text, guild.members if guild else ())
    if user == None:
        raise util.discord.UserError(
            "Multiple or no results for user {}".format(
                util.discord.Inline(arg.text)))
    return user.id

def role_id_from_arg(guild, arg):
    if isinstance(arg, plugins.commands.RoleMentionArg):
        return arg.id
    if not isinstance(arg, plugins.commands.StringArg): return None
    role = util.discord.smart_find(arg.text, guild.roles if guild else ())
    if role == None:
        raise util.discord.UserError(
            "Multiple or no results for user {}".format(
                util.discord.Inline(arg.text)))
    return role.id

@plugins.commands.command("priv")
@priv("shell")
async def priv_command(msg, args):
    cmd = args.next_arg()
    if not isinstance(cmd, plugins.commands.StringArg): return

    if cmd.text.lower() == "new":
        priv = args.next_arg()
        if not isinstance(priv, plugins.commands.StringArg): return
        if conf[priv.text] != None:
            return await msg.channel.send(
                "Priv {} already exists".format(util.discord.Inline(priv.text)))
        conf[priv.text] = {"users": [], "roles": []}
        await msg.channel.send(
            "Created priv {}".format(util.discord.Inline(priv.text)))

    elif cmd.text.lower() == "delete":
        priv = args.next_arg()
        if not isinstance(priv, plugins.commands.StringArg): return
        if conf[priv.text] == None:
            return await msg.channel.send(
                "Priv {} does not exist".format(util.discord.Inline(priv.text)))
        conf[priv.text] = None
        await msg.channel.send(
            "Removed priv {}".format(util.discord.Inline(priv.text)))

    elif cmd.text.lower() == "show":
        priv = args.next_arg()
        if not isinstance(priv, plugins.commands.StringArg): return
        obj = conf[priv.text]
        if obj == None:
            await msg.channel.send(
                "Priv {} does not exist".format(util.discord.Inline(priv.text)))
        output = []
        if "users" in obj:
            for id in obj["users"]:
                member = discord.utils.find(lambda m: m.id == id,
                    msg.guild.members if msg.guild else ())
                if member:
                    member = "{}#{}({})".format(
                        member.nick or member.name,
                        member.discriminator, member.id)
                else:
                    member = "{}".format(id)
                output.append("user {}".format(util.discord.Inline(member)))
        if "roles" in obj:
            for id in obj["roles"]:
                role = discord.utils.find(lambda r: r.id == id,
                    msg.guild.roles if msg.guild else ())
                if role:
                    role = "{}({})".format(role.name, role.id)
                else:
                    role = "{}".format(id)
                output.append("role {}".format(util.discord.Inline(role)))
        await msg.channel.send(
            "Priv {} includes: {}".format(util.discord.Inline(priv.text),
                "; ".join(output)))

    elif cmd.text.lower() == "add":
        priv = args.next_arg()
        if not isinstance(priv, plugins.commands.StringArg): return
        obj = conf[priv.text]
        if obj == None:
            await msg.channel.send(
                "Priv {} does not exist".format(util.discord.Inline(priv.text)))
        cmd = args.next_arg()
        if not isinstance(cmd, plugins.commands.StringArg): return
        if cmd.text.lower() == "user":
            user_id = user_id_from_arg(msg.guild, args.next_arg())
            if user_id == None: return
            if user_id in obj.get("users", []):
                return await msg.channel.send(
                    "User {} is already in priv {}".format(user_id,
                        util.discord.Inline(priv.text)))

            obj = dict(obj)
            obj["users"] = obj.get("users", []) + [user_id]
            conf[priv.text] = obj

            await msg.channel.send(
                "Added user {} to priv {}".format(user_id,
                    util.discord.Inline(priv.text)))

        elif cmd.text.lower() == "role":
            role_id = role_id_from_arg(msg.guild, args.next_arg())
            if role_id == None: return
            if role_id in obj.get("roles", []):
                return await msg.channel.send(
                    "Role {} is already in priv {}".format(role_id,
                        util.discord.Inline(priv.text)))

            obj = dict(obj)
            obj["roles"] = obj.get("roles", []) + [role_id]
            conf[priv.text] = obj

            await msg.channel.send(
                "Added role {} to priv {}".format(role_id,
                    util.discord.Inline(priv.text)))

    elif cmd.text.lower() == "remove":
        priv = args.next_arg()
        if not isinstance(priv, plugins.commands.StringArg): return
        obj = conf[priv.text]
        if obj == None:
            await msg.channel.send(
                "Priv {} does not exist".format(util.discord.Inline(priv.text)))
        cmd = args.next_arg()
        if not isinstance(cmd, plugins.commands.StringArg): return
        if cmd.text.lower() == "user":
            user_id = user_id_from_arg(msg.guild, args.next_arg())
            if user_id == None: return
            if user_id not in obj.get("users", []):
                return await msg.channel.send(
                    "User {} is already not in priv {}".format(user_id,
                        util.discord.Inline(priv.text)))

            obj = dict(obj)
            obj["users"] = list(filter(lambda i: i != user_id,
                obj.get("users", [])))
            conf[priv.text] = obj

            await msg.channel.send(
                "Removed user {} from priv {}".format(user_id,
                    util.discord.Inline(priv.text)))

        elif cmd.text.lower() == "role":
            role_id = role_id_from_arg(msg.guild, args.next_arg())
            if role_id == None: return
            if role_id not in obj.get("roles", []):
                return await msg.channel.send(
                    "Role {} is already not in priv {}".format(role_id,
                        util.discord.Inline(priv.text)))

            obj = dict(obj)
            obj["roles"] = list(filter(lambda i: i != role_id,
                obj.get("roles", [])))
            conf[priv.text] = obj

            await msg.channel.send(
                "Removed role {} from priv {}".format(role_id,
                    util.discord.Inline(priv.text)))
