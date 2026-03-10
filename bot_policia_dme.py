"""
╔══════════════════════════════════════════════════════════════╗
║         🚔 BOT COMPLETO - POLÍCIA DME 🚔                    ║
║                                                              ║
║  FUNCIONALIDADES:                                            ║
║  ✅ Boas-vindas com embed bonito                             ║
║  ✅ Auto-cargo de Visitante ao entrar                        ║
║  ✅ Sistema de verificação (!verificar)                      ║
║  ✅ Reaction Roles (cargos por reação)                       ║
║  ✅ Contador de membros automático                           ║
║  ✅ Log de entradas e saídas                                 ║
║  ✅ Sistema de denúncias                                     ║
║  ✅ Ranking de atividade (XP)                                ║
║  ✅ Comandos de moderação                                    ║
║                                                              ║
║  INSTRUÇÕES:                                                 ║
║  1. pip install discord.py                                   ║
║  2. Cole TOKEN e GUILD_ID abaixo                             ║
║  3. python bot_policia_dme.py                                ║
╚══════════════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands, tasks
import asyncio
import json
import os
from datetime import datetime

# ══════════════════════════════════════════
#   ⚙️  CONFIGURAÇÕES — EDITE AQUI
# ══════════════════════════════════════════
TOKEN    = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "1480674787922808985"))

# Nomes dos canais (devem existir no servidor)
CANAL_BOAS_VINDAS   = "🏅・identificação"
CANAL_LOG           = "🏅・auditoria"
CANAL_DENUNCIAS     = "📢・solicitar-cargos"
CANAL_REACTION      = "🏅・identificação"
CANAL_MEMBROS_NOME  = "👮 Membros: {count}"  # nome do canal contador

# Cargos automáticos
CARGO_ENTRADA = "👤 Visitante"      # cargo dado ao entrar
CARGO_VERIFICADO = "🪖 Militar"     # cargo dado após aprovação
CARGO_ADMIN = "Administrador"    # cargo com total autonomia

# XP
XP_POR_MENSAGEM = 10
XP_COOLDOWN_SEGUNDOS = 60
# ══════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ── Armazenamento em memória ──────────────
xp_data = {}        # {user_id: {"xp": 0, "level": 1}}
xp_cooldown = {}    # {user_id: timestamp}
reaction_roles = {} # {message_id: {emoji: role_name}}

def xp_arquivo():
    return "xp_data.json"

def carregar_xp():
    global xp_data
    if os.path.exists(xp_arquivo()):
        with open(xp_arquivo(), "r") as f:
            xp_data = json.load(f)

def salvar_xp():
    with open(xp_arquivo(), "w") as f:
        json.dump(xp_data, f)

def xp_para_level(level):
    return level * 100

def cor_policia():
    return discord.Color.from_rgb(26, 58, 107)  # Azul polícia


# ══════════════════════════════════════════
#   🤖  EVENTOS
# ══════════════════════════════════════════

@bot.event
async def on_ready():
    carregar_xp()
    atualizar_contador.start()
    print(f"\n{'═'*50}")
    print(f"  🚔 BOT ONLINE: {bot.user}")
    print(f"  🏠 Servidor: {bot.get_guild(GUILD_ID)}")
    print(f"  📦 Guilds conectadas: {[g.name for g in bot.guilds]}")
    if not bot.get_guild(GUILD_ID):
        print(f"  ⚠️ AVISO: Não encontrei o ID {GUILD_ID} na lista de guilds!")
    print(f"{'═'*50}\n")
    
    # Registra a view do botão de identificação para ser persistente (funcionar após reiniciar)
    bot.add_view(BotaoVerificacao())
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🚔 Polícia DME"
        )
    )


# ── Boas-vindas + Auto-cargo ──────────────
@bot.event
async def on_member_join(member):
    guild = member.guild

    # 1. Dar cargo de Visitante automaticamente
    cargo = discord.utils.get(guild.roles, name=CARGO_ENTRADA)
    if cargo:
        await member.add_roles(cargo)

    # Envia embed de boas-vindas
    canal = discord.utils.get(guild.text_channels, name=CANAL_BOAS_VINDAS)
    if not canal:
        # Busca flexível (ignora emojis/ícones se houver)
        canal = next((c for c in guild.text_channels if CANAL_BOAS_VINDAS in c.name), None)
    
    if canal:
        embed = discord.Embed(
            title="👮 NOVO RECRUTA DETECTADO!",
            description=(
                f"**{member.mention}** acabou de entrar na **Polícia DME**!\n\n"
                f"📋 Leia as **#regras** antes de qualquer coisa.\n"
                f"🪪 Identifique-se neste canal para receber seu cargo.\n"
                f"🎖️ Boa sorte na sua jornada policial!"
            ),
            color=cor_policia(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Membro #{guild.member_count} • Polícia DME")
        embed.add_field(name="👤 Usuário", value=str(member), inline=True)
        embed.add_field(name="📅 Entrou em", value=datetime.now().strftime("%d/%m/%Y %H:%M"), inline=True)
        await canal.send(embed=embed)

    # Log de entrada
    log = discord.utils.get(guild.text_channels, name=CANAL_LOG)
    if not log:
        log = next((c for c in guild.text_channels if "auditoria" in c.name), None)
    
    if log:
        embed_log = discord.Embed(
            title="📥 Membro Entrou",
            description=f"{member.mention} (`{member}`) entrou no servidor.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed_log.set_thumbnail(url=member.display_avatar.url)
        embed_log.set_footer(text=f"ID: {member.id}")
        await log.send(embed=embed_log)


# ── Log de saída ──────────────────────────
@bot.event
async def on_member_remove(member):
    guild = member.guild
    log = discord.utils.get(guild.text_channels, name=CANAL_LOG)
    if not log:
        log = next((c for c in guild.text_channels if "auditoria" in c.name), None)
    if log:
        embed_log = discord.Embed(
            title="📤 Membro Saiu",
            description=f"**{member}** saiu do servidor.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed_log.set_thumbnail(url=member.display_avatar.url)
        embed_log.set_footer(text=f"ID: {member.id}")
        await log.send(embed=embed_log)


# ── Sistema de XP ─────────────────────────
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = str(message.author.id)
    agora = asyncio.get_event_loop().time()

    # XP com cooldown
    ultimo = xp_cooldown.get(uid, 0)
    if agora - ultimo >= XP_COOLDOWN_SEGUNDOS:
        xp_cooldown[uid] = agora
        if uid not in xp_data:
            xp_data[uid] = {"xp": 0, "level": 1}

        xp_data[uid]["xp"] += XP_POR_MENSAGEM
        xp_necessario = xp_para_level(xp_data[uid]["level"])

        if xp_data[uid]["xp"] >= xp_necessario:
            xp_data[uid]["level"] += 1
            xp_data[uid]["xp"] = 0
            salvar_xp()
            embed = discord.Embed(
                title="🎖️ SUBIU DE NÍVEL!",
                description=f"Parabéns {message.author.mention}! Você chegou ao **Nível {xp_data[uid]['level']}**!",
                color=discord.Color.gold()
            )
            await message.channel.send(embed=embed)
        else:
            salvar_xp()

    await bot.process_commands(message)


# ── Reaction Roles ────────────────────────
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    msg_id = str(payload.message_id)
    if msg_id not in reaction_roles:
        return
    emoji = str(payload.emoji)
    role_name = reaction_roles[msg_id].get(emoji)
    if not role_name:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role = discord.utils.get(guild.roles, name=role_name)
    if role and member:
        await member.add_roles(role)


@bot.event
async def on_raw_reaction_remove(payload):
    msg_id = str(payload.message_id)
    if msg_id not in reaction_roles:
        return
    emoji = str(payload.emoji)
    role_name = reaction_roles[msg_id].get(emoji)
    if not role_name:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role = discord.utils.get(guild.roles, name=role_name)
    if role and member:
        await member.remove_roles(role)


# ══════════════════════════════════════════
#   📋  COMANDOS
# ══════════════════════════════════════════

# ── Lista de todos os cargos disponíveis ──
CARGOS_DISPONIVEIS = [
    ("☠️ GOE",               "GOE"),
    ("🦅 ABIN",              "ABIN"),
    ("🪖 CIGS",              "CIGS"),
    ("💰 Auditoria Fiscal",  "Auditoria Fiscal"),
    ("🎮 Agência de Eventos","Agência de Eventos"),
    ("📱CDT",               "CDT"),
    ("✎ Centro de Recursos Humanos ✎", "CRH"),
    ("🗂️ Centro de Normas e Desligamentos", "CND"),
    ("📸 APM",               "APM"),
    ("✨AMAN",               "AMAN"),
    ("🕵🏿‍♀️Praça de Elite",  "PE"),
    ("🥇 MNP",               "MNP"),
    ("🔱 COR",               "COR"),
    ("☬ Conselho do C.E ☬",  "Conselho"),
    ("⚜️ Ministério Público", "Ministério Público"),
    ("🔱 Corregedoria",      "Corregedoria"),
    ("👑 Supremacia",        "Supremacia"),
]

# ── Passo 1: Modal com dados básicos ──────
class FormularioDados(discord.ui.Modal, title="🚔 Identificação — Dados"):

    nick_habbo = discord.ui.TextInput(
        label="Nickname no Habbo",
        placeholder="Ex: Xandeuss",
        required=True,
        max_length=30
    )

    # link_foto Removido para automação via API do Habbo

    async def on_submit(self, interaction: discord.Interaction):
        cargo_v = discord.utils.get(interaction.guild.roles, name=CARGO_VERIFICADO)
        if cargo_v and cargo_v in interaction.user.roles:
            await interaction.response.send_message("⚠️ Você já está identificado!", ephemeral=True)
            return
        # Gera link da foto automaticamente via API do Habbo
        foto_automatica = f"https://www.habbo.com.br/habbo-imaging/avatarimage?user={self.nick_habbo.value}&direction=4&head_direction=4&action=std&gesture=std&size=l"
        
        # Passa para o passo 2: seleção de cargos
        view = SelecaoCargos(self.nick_habbo.value, foto_automatica)
        await interaction.response.send_message(
            "## 🎖️ Selecione os cargos que você faz parte:\n"
            "*(Selecione todos que se aplicam e clique em **Enviar**)*",
            view=view,
            ephemeral=True
        )


# ── Passo 2: Dropdown de seleção de cargos ─
class SelecaoCargos(discord.ui.View):
    def __init__(self, nick: str, foto: str):
        super().__init__(timeout=300)
        self.nick = nick
        self.foto = foto
        self.cargos_selecionados = []
        self.add_item(DropdownCargos(nick, foto))


class DropdownCargos(discord.ui.Select):
    def __init__(self, nick: str, foto: str):
        self.nick_salvo = nick
        self.foto_salva = foto
        options = [
            discord.SelectOption(label=label, value=valor)
            for label, valor in CARGOS_DISPONIVEIS
        ]
        super().__init__(
            placeholder="🎖️ Selecione seus cargos...",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        cargos_escolhidos = self.values
        guild = interaction.guild
        membro = interaction.user

        # Monta lista dos nomes completos dos cargos
        nomes_cargos = []
        for label, valor in CARGOS_DISPONIVEIS:
            if valor in cargos_escolhidos:
                nomes_cargos.append(label)

        # Envia para auditoria
        canal_audit = discord.utils.get(guild.text_channels, name=CANAL_LOG)
        if canal_audit:
            embed = discord.Embed(
                title="📋 NOVA SOLICITAÇÃO DE IDENTIFICAÇÃO",
                description=f"**{membro.mention}** (`{membro}`) quer entrar na Polícia DME!",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="🪪 Nick no Habbo", value=self.nick_salvo, inline=True)
            embed.add_field(name="🎖️ Cargos solicitados", value="\n".join(nomes_cargos), inline=True)
            embed.add_field(name="🖼️ Foto do perfil", value=self.foto_salva, inline=False)
            embed.set_footer(text=f"ID: {membro.id}")
            if self.foto_salva.startswith("http"):
                embed.set_image(url=self.foto_salva)

            view = BotoesAprovacao(membro.id, self.nick_salvo, nomes_cargos)
            await canal_audit.send(embed=embed, view=view)

        await interaction.response.edit_message(
            content="✅ **Solicitação enviada com sucesso!**\nUm superior irá analisar e aprovar em breve. Aguarde! 🚔",
            view=None
        )


# ── Botões de Aprovação/Reprovação ─────────
class BotoesAprovacao(discord.ui.View):
    def __init__(self, membro_id: int, nick: str, cargos: list):
        super().__init__(timeout=None)
        self.membro_id = membro_id
        self.nick = nick
        self.cargos = cargos  # lista de nomes completos ex: ["🏆 GOE", "📋 CDT"]

    @discord.ui.button(label="✅ APROVAR", style=discord.ButtonStyle.success, emoji="✅")
    async def aprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        membro = guild.get_member(self.membro_id)

        if not membro:
            await interaction.response.send_message("❌ Membro não encontrado no servidor.", ephemeral=True)
            return

        cargos_dados = []

        # Dá cargo de Militar
        cargo_v = discord.utils.get(guild.roles, name=CARGO_VERIFICADO)
        cargo_e = discord.utils.get(guild.roles, name=CARGO_ENTRADA)
        if cargo_v:
            await membro.add_roles(cargo_v)
            cargos_dados.append(CARGO_VERIFICADO)
        if cargo_e:
            await membro.remove_roles(cargo_e)

        # Dá todos os cargos selecionados
        for nome_cargo in self.cargos:
            role = discord.utils.get(guild.roles, name=nome_cargo)
            if role:
                await membro.add_roles(role)
                cargos_dados.append(nome_cargo)

        # Renomeia nick
        try:
            await membro.edit(nick=f"[DME] {self.nick}")
        except:
            pass

        embed_ok = discord.Embed(
            title="✅ IDENTIFICAÇÃO APROVADA",
            description=(
                f"**{membro.mention}** aprovado por {interaction.user.mention}!\n\n"
                f"🪪 Nick: **{self.nick}**\n"
                f"🎖️ Cargos concedidos:\n" + "\n".join(f"• {c}" for c in cargos_dados)
            ),
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed_ok.set_footer(text=f"Aprovado por: {interaction.user}")
        await interaction.message.edit(embed=embed_ok, view=None)

        # DM para o membro
        try:
            dm = discord.Embed(
                title="🎉 IDENTIFICAÇÃO APROVADA!",
                description=(
                    f"Bem-vindo(a) à **Polícia DME**, **{self.nick}**!\n\n"
                    f"🎖️ Cargos recebidos:\n" + "\n".join(f"• {c}" for c in cargos_dados) +
                    f"\n\nBoa sorte na corporação! 🚔"
                ),
                color=discord.Color.green()
            )
            await membro.send(embed=dm)
        except:
            pass

        await interaction.response.send_message(
            f"✅ {membro.mention} aprovado com {len(cargos_dados)} cargos!", ephemeral=True
        )

    @discord.ui.button(label="❌ REPROVAR", style=discord.ButtonStyle.danger, emoji="❌")
    async def reprovar(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        membro = guild.get_member(self.membro_id)

        embed_neg = discord.Embed(
            title="❌ IDENTIFICAÇÃO REPROVADA",
            description=(
                f"**{membro.mention if membro else self.membro_id}** reprovado por {interaction.user.mention}.\n"
                f"🪪 Nick: **{self.nick}**"
            ),
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed_neg.set_footer(text=f"Reprovado por: {interaction.user}")
        await interaction.message.edit(embed=embed_neg, view=None)

        if membro:
            try:
                await membro.send(
                    "❌ Sua identificação na **Polícia DME** foi **reprovada**.\n"
                    "Entre em contato com um superior para mais informações."
                )
            except:
                pass

        await interaction.response.send_message("❌ Solicitação reprovada.", ephemeral=True)


# ── Botão que abre o formulário ────────────
class BotaoVerificacao(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🪪 IDENTIFICAR-SE",
        style=discord.ButtonStyle.success,
        custom_id="verificar_btn",
        emoji="🚔"
    )
    async def verificar_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FormularioDados())


@bot.command(name="setupverificacao")
@commands.has_permissions(administrator=True)
async def setupverificacao(ctx):
    """Envia a mensagem com botão de verificação no canal"""
    embed = discord.Embed(
        title="🚔 IDENTIFICAÇÃO — POLÍCIA DME",
        description=(
            "Bem-vindo(a) à **Polícia DME**!\n\n"
            "📋 Para solicitar acesso ao servidor, clique no botão abaixo.\n"
            "📝 Preencha o formulário com seus dados do Habbo.\n"
            "✅ Um superior irá analisar e aprovar sua entrada.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=cor_policia()
    )
    embed.set_footer(text="🚔 Polícia DME • Clique no botão para se identificar")
    await ctx.send(embed=embed, view=BotaoVerificacao())
    await ctx.message.delete()


# ── !verificar ────────────────────────────
@bot.command(name="verificar")
async def verificar(ctx, *, nick_habbo: str = None):
    """Membro se verifica informando o nick do Habbo"""
    if not nick_habbo:
        await ctx.send("❌ Use: `!verificar SeuNickHabbo`")
        return

    cargo_v = discord.utils.get(ctx.guild.roles, name=CARGO_VERIFICADO)
    cargo_e = discord.utils.get(ctx.guild.roles, name=CARGO_ENTRADA)

    if cargo_v:
        await ctx.author.add_roles(cargo_v)
    if cargo_e:
        await ctx.author.remove_roles(cargo_e)

    try:
        await ctx.author.edit(nick=f"[DME] {nick_habbo}")
    except:
        pass

    embed = discord.Embed(
        title="✅ VERIFICADO!",
        description=f"{ctx.author.mention} foi verificado como **{nick_habbo}** na Polícia DME!",
        color=discord.Color.green()
    )
    embed.set_footer(text="Bem-vindo à Polícia DME!")
    await ctx.send(embed=embed)
    await ctx.message.delete()


# ── !rank ─────────────────────────────────
@bot.command(name="rank")
async def rank(ctx, membro: discord.Member = None):
    """Mostra o rank de XP de um membro"""
    membro = membro or ctx.author
    uid = str(membro.id)
    dados = xp_data.get(uid, {"xp": 0, "level": 1})
    xp_atual = dados["xp"]
    level = dados["level"]
    xp_prox = xp_para_level(level)
    progresso = int((xp_atual / xp_prox) * 20)
    barra = "█" * progresso + "░" * (20 - progresso)

    embed = discord.Embed(
        title=f"🎖️ Rank de {membro.display_name}",
        color=cor_policia()
    )
    embed.set_thumbnail(url=membro.display_avatar.url)
    embed.add_field(name="🏅 Nível", value=str(level), inline=True)
    embed.add_field(name="⭐ XP", value=f"{xp_atual}/{xp_prox}", inline=True)
    embed.add_field(name="📊 Progresso", value=f"`{barra}`", inline=False)
    await ctx.send(embed=embed)


# ── !top ──────────────────────────────────
@bot.command(name="top")
async def top(ctx):
    """Top 10 membros mais ativos"""
    if not xp_data:
        await ctx.send("❌ Ainda não há dados de XP!")
        return

    ranking = sorted(xp_data.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    embed = discord.Embed(title="🏆 TOP 10 MAIS ATIVOS", color=cor_policia())
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

    desc = ""
    for i, (uid, dados) in enumerate(ranking):
        membro = ctx.guild.get_member(int(uid))
        nome = membro.display_name if membro else f"ID:{uid}"
        desc += f"{medals[i]} **{nome}** — Nível {dados['level']} ({dados['xp']} XP)\n"

    embed.description = desc
    await ctx.send(embed=embed)


# ── !denunciar ────────────────────────────
@bot.command(name="denunciar")
async def denunciar(ctx, acusado: discord.Member = None, *, motivo: str = None):
    """Faz uma denúncia anônima"""
    if not acusado or not motivo:
        await ctx.send("❌ Use: `!denunciar @usuário motivo`")
        return

    canal = discord.utils.get(ctx.guild.text_channels, name=CANAL_DENUNCIAS)
    if not canal:
        canal = next((c for c in ctx.guild.text_channels if "solicitar-cargos" in c.name), None)
    
    if canal:
        embed = discord.Embed(
            title="🚨 NOVA DENÚNCIA",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="👤 Acusado", value=f"{acusado.mention} (`{acusado}`)", inline=False)
        embed.add_field(name="📋 Motivo", value=motivo, inline=False)
        embed.add_field(name="📅 Data", value=datetime.now().strftime("%d/%m/%Y %H:%M"), inline=True)
        embed.set_footer(text="Denúncia enviada anonimamente")
        await canal.send(embed=embed)

    await ctx.message.delete()
    await ctx.author.send("✅ Sua denúncia foi enviada com sucesso!")


# ── !reactionrole ─────────────────────────
@bot.command(name="reactionrole")
@commands.has_permissions(administrator=True)
async def reactionrole(ctx, emoji: str, *, cargo: str):
    """Cria mensagem de reaction role. Ex: !reactionrole 🎖️ Policial"""
    role = discord.utils.get(ctx.guild.roles, name=cargo)
    if not role:
        await ctx.send(f"❌ Cargo `{cargo}` não encontrado!")
        return

    embed = discord.Embed(
        title="🎭 SELEÇÃO DE CARGO",
        description=f"Reaja com {emoji} para receber o cargo **{cargo}**!",
        color=cor_policia()
    )
    msg = await ctx.send(embed=embed)
    await msg.add_reaction(emoji)
    reaction_roles[str(msg.id)] = {emoji: cargo}
    await ctx.message.delete()


# ── !kick / !ban ──────────────────────────
@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, membro: discord.Member, *, motivo="Sem motivo"):
    await membro.kick(reason=motivo)
    embed = discord.Embed(title="👢 Membro Expulso", description=f"{membro} foi expulso.\n**Motivo:** {motivo}", color=discord.Color.orange())
    await ctx.send(embed=embed)

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, membro: discord.Member, *, motivo="Sem motivo"):
    await membro.ban(reason=motivo)
    embed = discord.Embed(title="🔨 Membro Banido", description=f"{membro} foi banido.\n**Motivo:** {motivo}", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="limpar")
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int = 10):
    await ctx.channel.purge(limit=quantidade + 1)
    msg = await ctx.send(f"✅ {quantidade} mensagens deletadas!")
    await asyncio.sleep(3)
    await msg.delete()


# ── !cargo ────────────────────────────────
@bot.command(name="cargo")
@commands.has_permissions(manage_roles=True)
async def cargo(ctx, membro: discord.Member, *, nome_cargo: str):
    """Dá ou remove um cargo. Ex: !cargo @membro Policial"""
    role = discord.utils.get(ctx.guild.roles, name=nome_cargo)
    if not role:
        await ctx.send(f"❌ Cargo `{nome_cargo}` não encontrado!")
        return
    if role in membro.roles:
        await membro.remove_roles(role)
        await ctx.send(f"✅ Cargo **{nome_cargo}** removido de {membro.mention}!")
    else:
        await membro.add_roles(role)
        await ctx.send(f"✅ Cargo **{nome_cargo}** dado a {membro.mention}!")


# ── !ajuda ────────────────────────────────
@bot.command(name="ajuda")
async def ajuda(ctx):
    embed = discord.Embed(title="📋 COMANDOS DO BOT - POLÍCIA DME", color=cor_policia())
    embed.add_field(name="👤 Membros", value=(
        "`!verificar NickHabbo` — Verificar-se\n"
        "`!rank [@membro]` — Ver rank de XP\n"
        "`!top` — Top 10 mais ativos\n"
        "`!denunciar @membro motivo` — Denúncia anônima"
    ), inline=False)
    embed.add_field(name="🛡️ Moderação", value=(
        "`!cargo @membro Cargo` — Dar/remover cargo\n"
        "`!kick @membro` — Expulsar membro\n"
        "`!ban @membro` — Banir membro\n"
        "`!limpar [qtd]` — Limpar mensagens\n"
        "`!reactionrole emoji Cargo` — Criar reaction role"
    ), inline=False)
    embed.set_footer(text="🚔 Polícia DME • Bot Automático")
    await ctx.send(embed=embed)


# ══════════════════════════════════════════
#   ⏰  TAREFAS AUTOMÁTICAS
# ══════════════════════════════════════════

@tasks.loop(minutes=5)
async def atualizar_contador():
    """Atualiza canal com contador de membros"""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
    for canal in guild.voice_channels:
        if "Membros:" in canal.name:
            novo_nome = f"👮 Membros: {guild.member_count}"
            if canal.name != novo_nome:
                await canal.edit(name=novo_nome)
            break


# ══════════════════════════════════════════
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERRO: A variável de ambiente TOKEN não foi encontrada!")
    else:
        print("🚀 Iniciando Bot Polícia DME...")
        bot.run(TOKEN)
