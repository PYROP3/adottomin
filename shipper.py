import botlogger
import db
import discord
import bot_utils
import traceback
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
import PIL
import random
import string
import typing
import os
import math
import re

from netgraph import Graph

logger = botlogger.get_logger(__name__)

emoji_remover = re.compile("(:[^: ]+:)|(<a?:[^: ]+:[0-9]+>)|((<@[0-9]+>))")

# Commands
@discord.app_commands.guild_only()
class Relationship(discord.app_commands.Group):
    def __init__(self, database: db.database, utils: bot_utils.utils):
        super().__init__()
        self.database = database
        self.utils = utils
    
    @discord.app_commands.command(description='Create a relationship status between you and someone else')
    @discord.app_commands.describe(user='Who the relationship should be attached to', relation='What your relationship with them is')
    async def create(self, interaction: discord.Interaction, user: discord.Member, relation: str):
        logger.info(f"{interaction.user} requested creation of '{relation}' with {user}")

        if user.id == interaction.user.id:
            await self.utils.safe_send(interaction, content=f"You can't create a relationship with yourself, silly~!", ephemeral=True)
            return

        relation = emoji_remover.sub("", relation)

        if len(relation) == 0:
            await self.utils.safe_send(interaction, content=f"I have to remove stuff like emojis and user mentions from the text, silly~", ephemeral=True)
            return

        self.database.relationship_create_entry(interaction.user.id, user.id, relation)
        messaged = False
        try:
            lines = [
                f"Hey {user.nick or user.name}! {interaction.user} requested to register a '{relation}' relationship with you",
                f"You can approve this with /relationship approve {interaction.user.mention}",
                f"Or you can reject this with /relationship reject {interaction.user.mention}",
                f"**Please keep in mind that these commands _only work in the server_~**"
            ]
            await self.utils._split_dm("\n".join(lines), user)
            messaged = True
        except Exception as e:
            logger.warning(f"Error while trying to send DM to {user}: {e}\n{traceback.format_exc()}")

        content = f"Okay, I created a pending {relation} relationship between you and {user}. Now it's up to them to approve or reject it~"
        if not messaged:
            content += f"\nBtw, I wasn't able to message them directly, be sure to ask them to approve your request if possible~!"
        await self.utils.safe_send(interaction, content=content, ephemeral=True)
    
    @discord.app_commands.command(description='Approve the creation of a relationship status between someone else and you')
    @discord.app_commands.describe(user='Who requested the creation of a relationship with you')
    async def approve(self, interaction: discord.Interaction, user: discord.Member):
        logger.info(f"{interaction.user} requested approval of relationship with {user}")

        exists, is_pending, relation = self.database.relationship_is_pending(user.id, interaction.user.id)
        if not exists:
            content = f"Hmm. I couldn't find a relationship between you and {user.mention}... Try again, but keep in mind that you can't approve requests you created yourself"
        elif not is_pending:
            content = f"Your '{relation}' relationship with {user.mention} is already confirmed, b0ss~"
            content += f"\nKeep in mind you can always remove it with /relationship reject {user.mention} if needed, no questions asked!"
        else:
            self.database.relationship_confirm_entry(user.id, interaction.user.id)
            content = f"Your '{relation}' relationship with {user.mention} is confirmed, thanks for your input~"
            content += f"\nKeep in mind you can always remove it with /relationship reject {user.mention} if needed, no questions asked!"
            
        rev_exists, rev_is_pending, rev_relation = self.database.relationship_is_pending(interaction.user.id, user.id)
        if not rev_exists:
            content += f"\nBtw, you can register a relationship with {user} yourself using /relationship create {user.mention} <relation> :3"
        elif not rev_is_pending:
            content += f"\nBtw, the '{rev_relation}' you requested with them is still pending! Please ask them to approve or reject it if possible~ :3"
            
        await self.utils.safe_send(interaction, content=content, ephemeral=True)

        try:
            await self.utils._split_dm(f"Hey {user.nick or user.name}! {interaction.user} just approved your '{relation}' relationship with them~!", user)
        except Exception as e:
            logger.info(f"Error while trying to send DM to {user}: {e}\n{traceback.format_exc()}")
    
    @discord.app_commands.command(description='Reject or revoke a relationship status between someone else and you')
    @discord.app_commands.describe(user='Who requested the creation of a relationship with you')
    async def reject(self, interaction: discord.Interaction, user: discord.Member):
        logger.info(f"{interaction.user} requested removal of relationship with {user}")

        exists, is_pending, relation = self.database.relationship_is_pending(user.id, interaction.user.id)
        if not exists:
            content = f"Hmm. I couldn't find a relationship between you and {user.mention}... Try again, but keep in mind that you can't approve requests you created yourself"
        else:
            self.database.relationship_delete_entry(user.id, interaction.user.id)
            content = f"Your '{relation}' relationship with {user.mention} has been removed, thanks for your input~"
            
        rev_exists, rev_is_pending, rev_relation = self.database.relationship_is_pending(interaction.user.id, user.id)
        if not rev_exists:
            content += f"\nBtw, you can register a relationship with {user} yourself using /relationship create {user.mention} <relation> :3"
        elif not rev_is_pending:
            content += f"\nBtw, the '{rev_relation}' you requested with them is still pending! Please ask them to approve or reject it if possible~ :3"
            
        await self.utils.safe_send(interaction, content=content, ephemeral=True)

        try:
            keyword = 'rejected' if is_pending else 'removed'
            await self.utils._split_dm(f"Hey {user.nick or user.name}! {interaction.user} just {keyword} your '{relation}' relationship with them!", user)
        except Exception as e:
            logger.info(f"Error while trying to send DM to {user}: {e}\n{traceback.format_exc()}")
    
    @discord.app_commands.command(description='Create a visual relationship graph')
    #@discord.app_commands.describe(format='Whether to show only your circle, or the whole server')
    @discord.app_commands.describe(user='Whose relationships to show (defaults to yourself)')
    #@discord.app_commands.choices(format=[discord.app_commands.Choice(name=b, value=b) for b in ['mine', 'complete']])
    #async def display(self, interaction: discord.Interaction, format: discord.app_commands.Choice[str]):
    async def display(self, interaction: discord.Interaction, user: typing.Optional[discord.Member]=None):
        user = user or interaction.user
        logger.info(f"{interaction.user} requested display of relationship [{user}]")

        # if format.value == 'complete':
        #     await self.utils.safe_send(interaction, content="Not yet supported~", ephemeral=True)
        #     return

        await self.utils.safe_defer(interaction)

        data_as_source, data_as_target = self.database.relationship_get_centered(user.id)
        user_list = list(dict.fromkeys([user.id] + [l[0] for l in data_as_source] + [l[0] for l in data_as_target]))

        graph_data =  [(user.id, target, relation, confirmed) for target, relation, confirmed in data_as_source]
        graph_data += [(source, user.id, relation, confirmed) for source, relation, confirmed in data_as_target]

        who_dont = "You don't" if user.id == interaction.user.id else f"{user.mention} doesn't"
        if len(graph_data) == 0:
            await self.utils.safe_send(interaction, content=f"{who_dont} have any relationships registered, silly~", is_followup=True)
            return

        name = await self.graph_core(interaction, graph_data, user_list, center=user)
        if not name:
            await self.utils.safe_send(interaction, content=f"Something went wrong... :c", is_followup=True)
            return

        report_file = discord.File(name, filename=f"user_relationships.png")

        await self.utils.safe_send(interaction, content=f"Here you go~", file=report_file, is_followup=True)

        os.remove(name)
        
    @discord.app_commands.command(description='Create a visual relationship graph of the whole server')
    async def displayall(self, interaction: discord.Interaction):
        logger.info(f"{interaction.user} requested display of whole server")
        if not await self.utils.ensure_secretary(interaction): return

        # if format.value == 'complete':
        #     await self.utils.safe_send(interaction, content="Not yet supported~", ephemeral=True)
        #     return

        await self.utils.safe_defer(interaction)

        user_list, graph_data = self.database.relationship_get_complete()


        name = await self.graph_core(interaction, graph_data, user_list)
        if not name:
            await self.utils.safe_send(interaction, content=f"Something went wrong... :c", is_followup=True)
            return

        report_file = discord.File(name, filename=f"server_relationships.png")

        await self.utils.safe_send(interaction, content=f"Here you go~", file=report_file, is_followup=True)

        os.remove(name)

    async def graph_core(self, interaction: discord.Interaction, graph_data: list[tuple[int, int, str, bool]], user_list: list, center: typing.Optional[discord.Member]=None, icon_size: typing.Optional[float]=None):

        def _square_text(text):
            if ' ' not in text: return text
            split = text.split(' ')
            perm = math.floor(math.sqrt(len(split)))
            lines = len(split)//perm
            return '\n'.join([' '.join(split[i*perm:(i+1)*perm]) for i in range(lines)])

        def _crumble_text(text, nmax=13):
            if ' ' not in text: return text
            lines = []
            line = ''
            for word in text.split(' '):
                if line == '':
                    line = word
                    continue
                if len(line + ' ' + word) <= nmax:
                    line += ' ' + word
                    continue
                lines += [line]
                line = word
            if line:
                lines += [line]
            # logger.debug(f"Crumbled {text} to {lines}")
            return '\n'.join(lines)

        instance_name = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        os.mkdir(f"trash/{instance_name}/")
        incognito_img = PIL.Image.open("meme_stuff/incognito_user.png")

        # Generate the network graph
        G = nx.DiGraph()

        sq_factor = math.sqrt(len(user_list))
        c_sq_factor = max(int(sq_factor)-1, 1)
        member_list = {}
        for user in user_list:
            try:
                member = interaction.guild.get_member(user)
                if not member:
                    member = await interaction.guild.fetch_member(user)
                # logger.debug(f"Fetched member {member}")
                member_name = member.nick or member.name
                # Images for graph nodes
                icon_name = f"trash/{instance_name}/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10)) + ".png"
                if member.guild_avatar:
                    await member.guild_avatar.save(fp=icon_name)
                else:
                    await member.avatar.save(fp=icon_name)
                # Add member to graph
                G.add_node(member_name, image=PIL.Image.open(icon_name))

            except discord.NotFound:
                # logger.warning(f"Couldn't fetch user {user}")
                # member = None
                member_name = str(user)
                # icon_name = f"meme_stuff/incognito_user.png"
                # Add incognito member to graph
                # G.add_node(user, image=PIL.Image.open(icon_name))
                G.add_node(user)

            # logger.debug(f"G now has {len(G.nodes)} nodes")
            member_list[user] = member_name

        logger.debug(f"Processed {len(user_list)} users -> {len(member_list)} members")

        edge_widths = {}

        # network_scale = 32
        network_scale = 1
        # edge_f = 2 - 3/sq_factor
        edge_f = 3

        for source, target, relation, confirmed in graph_data:
            source_name = member_list[source]
            target_name = member_list[target]
            # logger.debug(f"Adding {relation} ({confirmed}) {source_name}->{target_name}")
            style = '-' if confirmed else '--'
            G.add_edge(source_name, target_name, label=_crumble_text(relation, nmax=13+c_sq_factor), style=style)
            edge_widths[(source_name, target_name)] = edge_f * network_scale if confirmed else 1

        # _s = sq_factor * 5 OK for n=21 (_s=22.9128)
        _s = sq_factor * 5 #13
        fsize = (_s, _s)
        # _s = int(100 / c_sq_factor**.7) OK for n=21 (fdpi=40.932)
        #fdpi = int(100 / c_sq_factor**.7) # fdpi = (80) works okayish 
        fdpi = 70 + int(1.5*math.sqrt(max(len(user_list)-3, 1)))
        
        # icon_scale = .4 OK for n=21
        icon_scale = 2 / sq_factor

        # fontsize = int(20 - 1. * math.sqrt(sq_factor)) #int(15 + 1.5 * c_sq_factor)
        fontsize = int(20 - .5 * sq_factor)

        # Get a layout and create figure
        if center:
            # radius = .3 * c_sq_factor OK for n=4 (radius=0.3)
            radius = 1.
            pos = nx.circular_layout(G, center=[0,0])
            center_key = center.nick or center.name
            pos[center_key] = np.array([0, 0])
            slots = len(member_list) - 1
            t = np.linspace(0, 2*np.pi, slots, endpoint=False)
            coss = np.cos(t)
            sins = np.sin(t)
            idx = 0
            for key in member_list.values():
                if key == center_key:
                    continue
                pos[key] = np.array([radius * coss[idx], radius * sins[idx]])
                # logger.debug(f"Figure pos for {key} ({idx}) = {pos[key]}")
                idx += 1
        else:
            # k=0.5*sq_factor OK for n=21 (k=2.291)
            # k = 10/sq_factor
            # k = 50 / len(user_list)
            # k = 2 + 1/sq_factor
            k = None
            # k = 1.2 / sq_factor
            iterations = 50
            pos = nx.spring_layout(G, k=k, iterations=iterations, scale=network_scale)

        cmap = plt.get_cmap('hsv')

        fig, ax = plt.subplots(figsize=fsize, dpi=fdpi)
        Graph(G, 
            node_layout=pos, 
            ax=ax,
            origin=(-1 * network_scale, -1 * network_scale),
            edge_color={edge: cmap(random.random()) for edge in edge_widths},
            edge_layout='curved',
            edge_layout_kwargs=dict(bundle_parallel_edges=False), 
            edge_width=edge_widths,
            edge_labels=nx.get_edge_attributes(G, 'label'), 
            edge_label_fontdict=dict(size=fontsize),
            node_edge_width=0.,
            node_alpha=0.,
            node_size=20. * icon_scale / network_scale,
            scale=(2 * network_scale, 2 * network_scale),
            arrows=True
        )

        # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
        tr_figure = ax.transData.transform
        # Transform from display to figure coordinates
        tr_axes = fig.transFigure.inverted().transform

        # Select the size of the image (relative to the X axis)
        icon_size = icon_size or (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.05
        icon_center = icon_size / 2.0

        # Add the respective image to each node
        size_factor = 1
        # for n in G.nodes:
        for n in member_list.values():
            xf, yf = tr_figure(pos[n])
            xa, ya = tr_axes((xf, yf))
            # logger.debug(f"Adding image for node {n} ({xa}, {ya})")
            # get overlapped axes and plot icon
            a = plt.axes(
                [
                    xa - (icon_center * size_factor * icon_scale / network_scale), 
                    ya - (icon_center * size_factor * icon_scale / network_scale), 
                    icon_size * size_factor * icon_scale * .9 / network_scale, 
                    icon_size * size_factor * icon_scale * .9 / network_scale
                ]
            )
            im = G.nodes[n]["image"] if "image" in G.nodes[n] else incognito_img
            a.imshow(im)
            # im = G.nodes[n]["image"] if "image" in G.nodes[n] else incognito_img
            # a.imshow(im)
            # a.imshow(G.nodes[n]["image"])
            a.axis("off")
            size_factor = 1

        name = f"trash/{instance_name}.png"
        plt.savefig(name, bbox_inches='tight')
        try:
            os.rmdir(f"trash/{instance_name}/")
        except:
            logger.warning(f"error in os.rmdir")
        return name

