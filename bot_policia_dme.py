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
CANAL_LOG           = "👀・auditoria-de-identificação"
CANAL_DENUNCIAS     = "📢・solicitar-cargos"
CANAL_REACTION      = "🏅・identificação"
CANAL_MEMBROS_NOME  = "👮 Membros: {count}"  # nome do canal contador

# Cargos automáticos
CARGO_ENTRADA = "👤 Visitante"      # cargo dado ao entrar
CARGO_VERIFICADO = "🇧🇷 Militares"     # cargo dado após aprovação
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
    # Registra as views persistentes
    bot.add_view(BotaoVerificacao())
    bot.add_view(MenuJogos())
    
    # Inicia as tarefas automáticas
    if not atualizar_contador.is_running():
        atualizar_contador.start()
    if not limpar_identificacao.is_running():
        limpar_identificacao.start()
    
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
        roles_para_adicionar = []

        # Identifica cargo de Militar e Visitante
        cargo_v = discord.utils.get(guild.roles, name=CARGO_VERIFICADO)
        cargo_e = discord.utils.get(guild.roles, name=CARGO_ENTRADA)

        if cargo_v:
            roles_para_adicionar.append(cargo_v)
            cargos_dados.append(CARGO_VERIFICADO)
        
        # Identifica todos os cargos extras selecionados
        for nome_cargo in self.cargos:
            role = discord.utils.get(guild.roles, name=nome_cargo)
            if role:
                roles_para_adicionar.append(role)
                cargos_dados.append(nome_cargo)

        # Adiciona todos os cargos de uma vez (mais estável)
        if roles_para_adicionar:
            await membro.add_roles(*roles_para_adicionar)

        # Remove cargo de entrada
        if cargo_e:
            await membro.remove_roles(cargo_e)

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


# ══════════════════════════════════════════
#   🕹️  SISTEMA DE JOGOS (BETA)
# ══════════════════════════════════════════

# --- Jogo da Velha (TicTacToe) ---

class TicTacToeButton(discord.ui.Button['TicTacToe']):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view = self.view

        # Validação: Só permite que o jogador da vez clique
        if view.current_player == view.X and interaction.user != view.player_x:
            return await interaction.response.send_message("Não é sua vez! (Vez do X)", ephemeral=True)
        if view.current_player == view.O and interaction.user != view.player_o:
            return await interaction.response.send_message("Não é sua vez! (Vez do O)", ephemeral=True)

        state = view.board[self.y][self.x]

        if view.current_player == view.X:
            self.style = discord.ButtonStyle.danger
            self.label = 'X'
            self.disabled = True
            view.board[self.y][self.x] = view.X
            view.current_player = view.O
            content = f"Vez de: **{view.player_o.display_name}** (O)"
        else:
            self.style = discord.ButtonStyle.success
            self.label = 'O'
            self.disabled = True
            view.board[self.y][self.x] = view.O
            view.current_player = view.X
            content = f"Vez de: **{view.player_x.display_name}** (X)"

        winner = view.check_board_winner()
        if winner is not None:
            if winner == view.X:
                content = f"🏆 **{view.player_x.display_name}** (X) VENCEU!"
            elif winner == view.O:
                content = f"🏆 **{view.player_o.display_name}** (O) VENCEU!"
            else:
                content = "🤝 **EMPATE!**"

            for child in view.children:
                child.disabled = True
            view.stop()

        await interaction.response.edit_message(content=content, view=view)


class TicTacToe(discord.ui.View):
    X = -1
    O = 1
    Tie = 2

    def __init__(self, player_x: discord.Member, player_o: discord.Member):
        super().__init__(timeout=600)
        self.current_player = self.X
        self.player_x = player_x
        self.player_o = player_o
        self.board = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_board_winner(self):
        for across in self.board:
            value = sum(across)
            if value == 3: return self.O
            if value == -3: return self.X

        for line in range(3):
            value = self.board[0][line] + self.board[1][line] + self.board[2][line]
            if value == 3: return self.O
            if value == -3: return self.X

        diag = self.board[0][0] + self.board[1][1] + self.board[2][2]
        if diag == 3: return self.O
        if diag == -3: return self.X

        diag = self.board[0][2] + self.board[1][1] + self.board[2][0]
        if diag == 3: return self.O
        if diag == -3: return self.X

        if all(all(row) for row in self.board):
            return self.Tie

        return None


# --- Lobby do Jogo ---

class LobbyTTT(discord.ui.View):
    def __init__(self, creator: discord.Member):
        super().__init__(timeout=300)
        self.players = [creator]
        self.max_players = 2

    def embed_lobby(self):
        lista_players = "\n".join([f"🎮 {p.display_name}" for p in self.players])
        embed = discord.Embed(
            title="🎮 LOBBY: Jogo da Velha",
            description=f"Aguardando jogadores ({len(self.players)}/{self.max_players})\n\n**Jogadores:**\n{lista_players}",
            color=cor_policia()
        )
        return embed

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.primary, emoji="➕")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            return await interaction.response.send_message("Você já está no lobby!", ephemeral=True)
        
        if len(self.players) >= self.max_players:
            return await interaction.response.send_message("O lobby está cheio!", ephemeral=True)

        self.players.append(interaction.user)
        await interaction.response.edit_message(embed=self.embed_lobby(), view=self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary, emoji="➖")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("Você não está no lobby!", ephemeral=True)
        
        self.players.remove(interaction.user)
        if not self.players:
            await interaction.response.edit_message(content="❌ Lobby fechado por falta de jogadores.", embed=None, view=None)
            self.stop()
            return
            
        await interaction.response.edit_message(embed=self.embed_lobby(), view=self)

    @discord.ui.button(label="INICIAR JOGO", style=discord.ButtonStyle.success, emoji="🚀")
    async def iniciar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.players) < self.max_players:
            return await interaction.response.send_message("Aguarde o segundo jogador entrar!", ephemeral=True)
        
        # Sorteia quem começa como X
        import random
        random.shuffle(self.players)
        p1, p2 = self.players[0], self.players[1]
        
        view_game = TicTacToe(p1, p2)
        await interaction.response.edit_message(
            content=f"🎮 **JOGO DA VELHA INICIADO!**\n**X:** {p1.mention}\n**O:** {p2.mention}\n\nVez de: **{p1.display_name}** (X)",
            embed=None,
            view=view_game
        )
        self.stop()


# --- Pedra, Papel e Tesoura (PPT) ---

class PPTGame(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=300)
        self.p1 = p1
        self.p2 = p2
        self.choices = {p1.id: None, p2.id: None}

    def get_winner(self):
        c1 = self.choices[self.p1.id]
        c2 = self.choices[self.p2.id]
        
        if c1 == c2: return "Empate"
        
        wins = {
            "pedra": "tesoura",
            "papel": "pedra",
            "tesoura": "papel"
        }
        
        if wins[c1] == c2:
            return self.p1
        return self.p2

    @discord.ui.button(label="Pedra", style=discord.ButtonStyle.secondary, emoji="🪨")
    async def pedra(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "pedra")

    @discord.ui.button(label="Papel", style=discord.ButtonStyle.secondary, emoji="📄")
    async def papel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "papel")

    @discord.ui.button(label="Tesoura", style=discord.ButtonStyle.secondary, emoji="✂️")
    async def tesoura(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "tesoura")

    async def process_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id not in self.choices:
            return await interaction.response.send_message("Você não está nesta partida!", ephemeral=True)
        
        if self.choices[interaction.user.id] is not None:
            return await interaction.response.send_message("Você já fez sua jogada!", ephemeral=True)

        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"Você escolheu {choice}!", ephemeral=True)

        # Verifica se ambos jogaram
        if all(self.choices.values()):
            winner = self.get_winner()
            c1 = self.choices[self.p1.id]
            c2 = self.choices[self.p2.id]
            
            emojis = {"pedra": "🪨", "papel": "📄", "tesoura": "✂️"}
            
            msg = (
                f"🎮 **RESULTADO: PEDRA, PAPEL E TESOURA**\n\n"
                f"{self.p1.mention} jogou {emojis[c1]} **{c1.upper()}**\n"
                f"{self.p2.mention} jogou {emojis[c2]} **{c2.upper()}**\n\n"
            )
            
            if winner == "Empate":
                msg += "🤝 **EMPATE!**"
            else:
                msg += f"🏆 **{winner.display_name} VENCEU!**"

            for child in self.children:
                child.disabled = True
            
            await interaction.message.edit(content=msg, view=None)
            self.stop()

class LobbyPPT(discord.ui.View):
    def __init__(self, creator: discord.Member):
        super().__init__(timeout=300)
        self.players = [creator]
        self.max_players = 2

    def embed_lobby(self):
        lista_players = "\n".join([f"🎮 {p.display_name}" for p in self.players])
        embed = discord.Embed(
            title="🎮 LOBBY: Pedra, Papel e Tesoura",
            description=f"Aguardando jogadores ({len(self.players)}/{self.max_players})\n\n**Jogadores:**\n{lista_players}",
            color=cor_policia()
        )
        return embed

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.primary, emoji="➕")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            return await interaction.response.send_message("Você já está no lobby!", ephemeral=True)
        
        if len(self.players) >= self.max_players:
            return await interaction.response.send_message("O lobby está cheio!", ephemeral=True)

        self.players.append(interaction.user)
        await interaction.response.edit_message(embed=self.embed_lobby(), view=self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary, emoji="➖")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("Você não está no lobby!", ephemeral=True)
        
        self.players.remove(interaction.user)
        if not self.players:
            await interaction.response.edit_message(content="❌ Lobby fechado.", embed=None, view=None)
            self.stop()
            return
            
        await interaction.response.edit_message(embed=self.embed_lobby(), view=self)

    @discord.ui.button(label="INICIAR JOGO", style=discord.ButtonStyle.success, emoji="🚀")
    async def iniciar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.players) < self.max_players:
            return await interaction.response.send_message("Aguarde o segundo jogador!", ephemeral=True)
        
        p1, p2 = self.players[0], self.players[1]
        view_game = PPTGame(p1, p2)
        await interaction.response.edit_message(
            content=f"🎮 **PEDRA, PAPEL E TESOURA INICIADO!**\n{p1.mention} vs {p2.mention}\n\n*Façam suas jogadas abaixo!*",
            embed=None,
            view=view_game
        )
        self.stop()


# --- Adivinhe o Número ---

class ChuteModal(discord.ui.Modal, title="Faça seu Chute!"):
    chute = discord.ui.TextInput(label="Qual é o número? (1-100)", placeholder="Digite um número...", min_length=1, max_length=3)

    def __init__(self, game_view):
        super().__init__()
        self.game_view = game_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            valor = int(self.chute.value)
        except ValueError:
            return await interaction.response.send_message("Isso não é um número válido!", ephemeral=True)

        await self.game_view.process_guess(interaction, valor)

class AdivinheJogo(discord.ui.View):
    def __init__(self, players: list):
        super().__init__(timeout=600)
        self.players = players
        import random
        self.secret_number = random.randint(1, 100)
        self.attempts = 0

    @discord.ui.button(label="Enviar Chute", style=discord.ButtonStyle.primary, emoji="🔢")
    async def chutar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("Você não está nesta partida!", ephemeral=True)
        await interaction.response.send_modal(ChuteModal(self))

    async def process_guess(self, interaction: discord.Interaction, guess: int):
        self.attempts += 1
        
        if guess == self.secret_number:
            # Venceu!
            global xp_data
            uid = str(interaction.user.id)
            if uid not in xp_data: xp_data[uid] = {"xp": 0, "level": 1}
            xp_data[uid]["xp"] += 50
            salvar_xp()

            embed = discord.Embed(
                title="🎉 TEMOS UM VENCEDOR!",
                description=(
                    f"**{interaction.user.mention}** acertou o número **{self.secret_number}**!\n"
                    f"📉 Tentativas totais: {self.attempts}\n"
                    f"🎁 Prêmio: **50 XP**"
                ),
                color=discord.Color.gold()
            )
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content="🎮 **FIM DE JOGO!**", embed=embed, view=None)
            self.stop()
        else:
            dica = "MAIOR ⬆️" if self.secret_number > guess else "MENOR ⬇️"
            await interaction.response.send_message(f"❌ O número {guess} está errado! É **{dica}**.", ephemeral=True)

class LobbyAdivinhe(discord.ui.View):
    def __init__(self, creator: discord.Member):
        super().__init__(timeout=300)
        self.players = [creator]
        self.max_players = 10

    def embed_lobby(self):
        lista = "\n".join([f"👤 {p.display_name}" for p in self.players])
        embed = discord.Embed(
            title="🎮 LOBBY: Adivinhe o Número",
            description=f"Aguardando jogadores (Mínimo 1, Máximo {self.max_players})\n\n**Jogadores:**\n{lista}",
            color=cor_policia()
        )
        return embed

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.primary, emoji="➕")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            return await interaction.response.send_message("Você já está no lobby!", ephemeral=True)
        if len(self.players) >= self.max_players:
            return await interaction.response.send_message("Lobby cheio!", ephemeral=True)
        self.players.append(interaction.user)
        await interaction.response.edit_message(embed=self.embed_lobby(), view=self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary, emoji="➖")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("Você não está aqui!", ephemeral=True)
        self.players.remove(interaction.user)
        if not self.players:
            await interaction.response.edit_message(content="❌ Lobby fechado.", embed=None, view=None)
            self.stop()
            return
        await interaction.response.edit_message(embed=self.embed_lobby(), view=self)

    @discord.ui.button(label="INICIAR JOGO", style=discord.ButtonStyle.success, emoji="🚀")
    async def iniciar(self, interaction: discord.Interaction, button: discord.ui.Button):
        game = AdivinheJogo(self.players)
        await interaction.response.edit_message(
            content="🎮 **O NÚMERO FOI ESCOLHIDO!**\nChute um valor de **1 a 100** clicando no botão abaixo.",
            embed=None,
            view=game
        )
        self.stop()


# --- Batalha Naval ---

class BatalhaNavalButton(discord.ui.Button['BatalhaNaval']):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view = self.view
        
        # Validação de turno
        if view.turno == 1 and interaction.user != view.p1:
            return await interaction.response.send_message("Não é sua vez! Espere o P1.", ephemeral=True)
        if view.turno == 2 and interaction.user != view.p2:
            return await interaction.response.send_message("Não é sua vez! Espere o P2.", ephemeral=True)

        target_board = view.board2 if view.turno == 1 else view.board1
        attacks = view.p1_attacks if view.turno == 1 else view.p2_attacks
        
        pos = (self.x, self.y)
        if pos in attacks:
            return await interaction.response.send_message("Você já atirou aqui!", ephemeral=True)

        attacks.add(pos)
        hit = pos in target_board
        
        if hit:
            self.style = discord.ButtonStyle.danger
            self.label = "💥"
            res_text = "FOGO! Você acertou um navio!"
        else:
            self.style = discord.ButtonStyle.primary
            self.label = "🌊"
            res_text = "ÁGUA... Você errou."

        # Verifica vitória
        hits_count = sum(1 for p in attacks if p in target_board)
        if hits_count == 3:
            winner = view.p1 if view.turno == 1 else view.p2
            for child in view.children:
                child.disabled = True
            await interaction.response.edit_message(content=f"🏆 **{winner.mention} AFUNDOU TODOS OS NAVIOS E VENCEU!**", view=view)
            view.stop()
            return

        # Muda turno
        view.turno = 2 if view.turno == 1 else 1
        proximo = view.p2 if view.turno == 2 else view.p1
        
        # Atualiza a view para o próximo jogador (esconde os tiros do anterior ou mantém?)
        # Para ser justo no mesmo canal, os botões mostram o histórico de TODOS os tiros.
        # Mas os botões clicados ficam desabilitados.
        self.disabled = True
        
        await interaction.response.edit_message(content=f"🎮 **BATALHA NAVAL**\n{res_text}\n\nVez de: {proximo.mention}", view=view)

class BatalhaNaval(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=600)
        self.p1 = p1
        self.p2 = p2
        self.turno = 1
        self.p1_attacks = set()
        self.p2_attacks = set()
        
        # Gera 3 navios aleatórios para cada (4x4)
        import random
        coords = [(x, y) for x in range(4) for y in range(4)]
        self.board1 = set(random.sample(coords, 3))
        self.board2 = set(random.sample(coords, 3))
        
        for y in range(4):
            for x in range(4):
                self.add_item(BatalhaNavalButton(x, y))

class LobbyNaval(discord.ui.View):
    def __init__(self, creator: discord.Member):
        super().__init__(timeout=300)
        self.players = [creator]
        self.max_players = 2

    def embed_lobby(self):
        lista = "\n".join([f"⚓ {p.display_name}" for p in self.players])
        embed = discord.Embed(
            title="🎮 LOBBY: Batalha Naval (4x4)",
            description=f"Aguardando oponente (1/{self.max_players})\n\n**Jogadores:**\n{lista}",
            color=cor_policia()
        )
        return embed

    @discord.ui.button(label="Entrar", style=discord.ButtonStyle.primary, emoji="➕")
    async def entrar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            return await interaction.response.send_message("Você já está no lobby!", ephemeral=True)
        self.players.append(interaction.user)
        await interaction.response.edit_message(embed=self.embed_lobby(), view=self)

    @discord.ui.button(label="Sair", style=discord.ButtonStyle.secondary, emoji="➖")
    async def sair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            return await interaction.response.send_message("Você não está aqui!", ephemeral=True)
        self.players.remove(interaction.user)
        if not self.players:
            await interaction.response.edit_message(content="❌ Lobby fechado.", embed=None, view=None)
            self.stop()
            return
        await interaction.response.edit_message(embed=self.embed_lobby(), view=self)

    @discord.ui.button(label="INICIAR GUERRA", style=discord.ButtonStyle.success, emoji="🚀")
    async def iniciar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.players) < 2:
            return await interaction.response.send_message("Aguarde um oponente!", ephemeral=True)
        
        p1, p2 = self.players[0], self.players[1]
        game = BatalhaNaval(p1, p2)
        await interaction.response.edit_message(
            content=f"⚓ **A GUERRA COMEÇOU!**\n{p1.mention} vs {p2.mention}\n\nVez de: {p1.mention}\n(Cada um tem 3 navios escondidos no grid 4x4)",
            embed=None,
            view=game
        )
        self.stop()


# --- Menu de Jogos ---

class MenuJogos(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="❌⭕ Jogo da Velha", style=discord.ButtonStyle.secondary, custom_id="jogos_ttt")
    async def jogo_da_velha(self, interaction: discord.Interaction, button: discord.ui.Button):
        lobby = LobbyTTT(interaction.user)
        await interaction.response.send_message(embed=lobby.embed_lobby(), view=lobby, ephemeral=False)

    @discord.ui.button(label="🪨📄 Pedra, Papel, Tesoura", style=discord.ButtonStyle.secondary, custom_id="jogos_ppt")
    async def pedra_papel_tesoura(self, interaction: discord.Interaction, button: discord.ui.Button):
        lobby = LobbyPPT(interaction.user)
        await interaction.response.send_message(embed=lobby.embed_lobby(), view=lobby, ephemeral=False)

    @discord.ui.button(label="🔢 Adivinhe o Número", style=discord.ButtonStyle.secondary, custom_id="jogos_adivinhe")
    async def adivinhe_numero(self, interaction: discord.Interaction, button: discord.ui.Button):
        lobby = LobbyAdivinhe(interaction.user)
        await interaction.response.send_message(embed=lobby.embed_lobby(), view=lobby, ephemeral=False)

    @discord.ui.button(label="⚓ Batalha Naval", style=discord.ButtonStyle.secondary, custom_id="jogos_naval")
    async def batalha_naval(self, interaction: discord.Interaction, button: discord.ui.Button):
        lobby = LobbyNaval(interaction.user)
        await interaction.response.send_message(embed=lobby.embed_lobby(), view=lobby, ephemeral=False)

@bot.command(name="setupjogos")
@commands.has_permissions(administrator=True)
async def setupjogos(ctx):
    """Envia o menu de jogos no canal"""
    embed = discord.Embed(
        title="🕹️ ÁREA DE LAZER - POLÍCIA DME",
        description=(
            "Bem-vindo ao canal de jogos! Aqui você pode relaxar e se divertir com seus colegas de farda.\n\n"
            "Escolha um jogo abaixo para criar um lobby:"
        ),
        color=cor_policia()
    )
    embed.set_footer(text="Aproveite com moderação! 🚔")
    await ctx.send(embed=embed, view=MenuJogos())
    await ctx.message.delete()


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

@tasks.loop(hours=24)
async def limpar_identificacao():
    """Limpa o canal de identificação a cada 24h, mantendo apenas a mensagem do botão"""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return
        
    canal = discord.utils.get(guild.text_channels, name=CANAL_BOAS_VINDAS)
    if not canal:
        canal = next((c for c in guild.text_channels if CANAL_BOAS_VINDAS in c.name), None)
        
    if canal:
        def check(m):
            # NÃO apaga se for a mensagem do bot que contém o título de IDENTIFICAÇÃO
            if m.author == bot.user and m.embeds and m.embeds[0].title == "🚔 IDENTIFICAÇÃO — POLÍCIA DME":
                return False
            return True

        try:
            deletadas = await canal.purge(limit=1000, check=check)
            print(f"🧹 Auto-limpeza: {len(deletadas)} mensagens removidas em {canal.name}")
        except Exception as e:
            print(f"❌ Erro na auto-limpeza: {e}")
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
