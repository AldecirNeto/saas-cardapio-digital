// =========================================================
// LÓGICA DO CLIENTE (Carrinho, Modais, Cupons e Fetch API)
// =========================================================

let saasDeviceId = localStorage.getItem("saas_device_id");
if (!saasDeviceId) {
    saasDeviceId = 'dev_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    localStorage.setItem("saas_device_id", saasDeviceId);
}

// ----------------------------------------------------
// LER MAIS (BALÃO DE DETALHES)
// ----------------------------------------------------
function abrirDetalhesProduto(elemento) {
    const titulo = elemento.getAttribute('data-titulo');
    const descricao = elemento.getAttribute('data-descricao');

    document.getElementById('detalhe-titulo').innerText = titulo;
    document.getElementById('detalhe-descricao').innerText = descricao;

    document.getElementById('modal-detalhes').classList.add('aberto');
    document.getElementById('overlay-detalhes').classList.add('ativo');
}

function fecharDetalhesProduto() {
    document.getElementById('modal-detalhes').classList.remove('aberto');
    document.getElementById('overlay-detalhes').classList.remove('ativo');
}

// ----------------------------------------------------
// INTERFACE: MENU E CARRINHO
// ----------------------------------------------------
function abrirMenu() {
    document.getElementById('menu-lateral').classList.add('aberta');
    document.getElementById('overlay-menu').classList.add('ativo');
}

function fecharMenu() {
    document.getElementById('menu-lateral').classList.remove('aberta');
    document.getElementById('overlay-menu').classList.remove('ativo');
}

function abrirCarrinho() {
    if(window.location.search.indexOf('cart=aberto') === -1) {
        window.location.href = window.location.pathname + "?cart=aberto";
    } else {
        document.getElementById('modal-carrinho').classList.add('aberto');
        document.getElementById('overlay-carrinho').classList.add('ativo');
        
        const telSalvo = localStorage.getItem("saas_tel_cliente") || "";
        if(telSalvo) {
            verificarRecompensasSilencioso(telSalvo);
        }
    }
}

function fecharCarrinho() {
    document.getElementById('modal-carrinho').classList.remove('aberto');
    document.getElementById('overlay-carrinho').classList.remove('ativo');
    history.replaceState(null, null, window.location.pathname);
}

window.onload = function() {
    if(window.location.search.includes("cart=aberto")) {
        document.getElementById('modal-carrinho').classList.add('aberto');
        document.getElementById('overlay-carrinho').classList.add('ativo');
    }
};

// ----------------------------------------------------
// ADICIONAR AO CARRINHO SILENCIOSAMENTE
// ----------------------------------------------------
async function adicionarItemSilencioso(event, form) {
    event.preventDefault(); 
    const btn = form.querySelector('.btn-add-form');
    const textoOriginal = btn.innerText;
    btn.innerText = "⏳...";

    try {
        const formData = new FormData(form);
        const url = form.getAttribute('action');
        
        const resposta = await fetch(url, { method: 'POST', body: formData });
        const dados = await resposta.json();

        document.getElementById('qtd-carrinho').innerText = dados.total_itens;

        const toast = document.getElementById('toast-aviso');
        toast.classList.add('mostrar');
        setTimeout(() => { toast.classList.remove('mostrar'); }, 2500);
        
        btn.innerText = textoOriginal;
        form.reset(); 
    } catch (erro) {
        console.error("Erro:", erro);
        btn.innerText = "Erro!";
    }
}

// SCROLL SPY DO MENU LATERAL
document.addEventListener("DOMContentLoaded", function(){
    const sessoes = document.querySelectorAll(".sessao-categoria");
    const linksMenu = document.querySelectorAll(".link-categoria");

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute("id");
                linksMenu.forEach(link => link.classList.remove("ativo"));
                const linkAtivo = document.querySelector(`.link-categoria[href="#${id}"]`);
                if (linkAtivo) linkAtivo.classList.add("ativo");
            }
        });
    }, { rootMargin: "-100px 0px -70% 0px" });

    sessoes.forEach(sessao => observer.observe(sessao));
});

// ----------------------------------------------------
// MOTOR DE CRM E CUPONS
// ----------------------------------------------------
document.addEventListener("DOMContentLoaded", function() {
    const hiddenDevice = document.getElementById("hiddenDeviceId");
    if(hiddenDevice) hiddenDevice.value = saasDeviceId;

    const nomeSalvo = localStorage.getItem("saas_nome_cliente");
    const telSalvo = localStorage.getItem("saas_tel_cliente") || ""; 
    
    if (nomeSalvo && document.getElementById("inputNomeCliente")) {
        document.getElementById("inputNomeCliente").value = nomeSalvo;
    }
    if (telSalvo && document.getElementById("inputTelCliente")) {
        document.getElementById("inputTelCliente").value = telSalvo;
    }
});

document.getElementById("inputTelCliente")?.addEventListener("blur", function() {
    const telDigitado = this.value.trim();
    if(telDigitado.length >= 10) { 
        verificarRecompensasSilencioso(telDigitado);
    }
});

function verificarRecompensasSilencioso(telefoneUsado) {
    const idRestaurante = document.getElementById("sys_restaurante_id")?.value;
    if (!idRestaurante) return;
    
    fetch('/api/verificar_recompensas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            telefone: telefoneUsado,
            restaurante_id: idRestaurante
        })
    })
    .then(res => res.json())
    .then(dados => {
        if(dados.status === "sucesso") {
            let msgMinimo = "";
            if (dados.valor_minimo > 0) {
                msgMinimo = `<br><span style="font-size: 13px; opacity: 0.9;">(Válido para pedidos acima de R$ ${dados.valor_minimo.toFixed(2)})</span>`;
            }

            let textoBanner = "";

            if (dados.tipo_limite === 'por_cliente') {
                textoBanner = `Este é o seu <strong>${dados.proximo_pedido}º pedido</strong> com a gente! <br>` +
                              `Como agradecimento, você ganhou <strong>${dados.texto_desconto}</strong>.`;
            } else {
                if (dados.limite_total > 0) {
                    textoBanner = `🔥 CORRE! Faltam apenas <strong>${dados.cupons_restantes} cupons</strong> de <strong>${dados.texto_desconto}</strong>!`;
                } else {
                    textoBanner = `🎉 Aproveite nosso cupom especial de <strong>${dados.texto_desconto}</strong> hoje!`;
                }
            }

            document.getElementById("texto-recompensa").innerHTML = textoBanner + msgMinimo;
            document.getElementById("codigo-recompensa").innerText = dados.codigo;
            document.getElementById("banner-recompensa").style.display = "block";
        }
    })
    .catch(err => console.log("Erro ao buscar recompensas.", err));
}

async function aplicarCupom() {
    const input = document.getElementById('inputCupom');
    const codigo = input.value.trim().toUpperCase();
    const btn = document.getElementById('btnCupom');
    const subtotal = parseFloat(document.getElementById('txtSubtotal').getAttribute('data-valor'));
    
    const inputTel = document.getElementById("inputTelCliente")?.value.trim();
    const telefoneParaValidar = inputTel || localStorage.getItem("saas_tel_cliente") || "";

    if(!codigo) {
        mostrarMsgCupom("Digite o código do cupom.", "#e74c3c");
        return;
    }

    if(!telefoneParaValidar) {
        mostrarMsgCupom("⚠️ Preencha seu telefone no formulário abaixo primeiro!", "#e67e22");
        document.getElementById("inputTelCliente").focus(); 
        document.getElementById("inputTelCliente").style.borderColor = "#e74c3c"; 
        return;
    } else {
        document.getElementById("inputTelCliente").style.borderColor = "var(--cor-primaria)";
    }

    btn.innerText = "⏳...";
    btn.disabled = true;

    try {
        const resposta = await fetch('/api/validar_cupom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                codigo: codigo,
                restaurante_id: document.getElementById("sys_restaurante_id").value,
                telefone: telefoneParaValidar,
                total: subtotal,
                device_id: saasDeviceId || "" 
            })
        });

        const dados = await resposta.json();

        if(dados.status === "sucesso") {
            mostrarMsgCupom("🎉 " + dados.mensagem, "#27ae60");
            aplicarDescontoVisual(dados.desconto, codigo);
        } else {
            mostrarMsgCupom("❌ " + dados.mensagem, "#e74c3c");
            removerDescontoVisual();
        }
    } catch (erro) {
        mostrarMsgCupom("❌ Erro ao validar o cupom. Tente novamente.", "#e74c3c");
        removerDescontoVisual();
    }

    if (document.getElementById('hiddenCupom').value === "") {
        btn.innerText = "Aplicar";
        btn.disabled = false;
    }
}

function mostrarMsgCupom(texto, cor) {
    const msg = document.getElementById('msgCupom');
    msg.innerText = texto;
    msg.style.color = cor;
    msg.style.display = "block";
}

function aplicarDescontoVisual(valorDesconto, codigo) {
    const subtotal = parseFloat(document.getElementById('txtSubtotal').getAttribute('data-valor'));
    let totalComDesconto = subtotal - valorDesconto;
    if(totalComDesconto < 0) totalComDesconto = 0; 

    document.getElementById('linhaDesconto').style.display = "flex";
    document.getElementById('txtDesconto').innerText = "- R$ " + valorDesconto.toFixed(2);
    document.getElementById('txtTotal').innerText = "R$ " + totalComDesconto.toFixed(2);
    
    document.getElementById('hiddenCupom').value = codigo;
    document.getElementById('inputCupom').readOnly = true;
    document.getElementById('btnCupom').innerText = "✔️ Aplicado";
    document.getElementById('btnCupom').style.background = "#27ae60";
}

function removerDescontoVisual() {
    const subtotal = parseFloat(document.getElementById('txtSubtotal').getAttribute('data-valor'));
    document.getElementById('linhaDesconto').style.display = "none";
    document.getElementById('txtTotal').innerText = "R$ " + subtotal.toFixed(2);
    document.getElementById('hiddenCupom').value = "";
}

document.getElementById("form-finalizar-pedido")?.addEventListener("submit", function() {
    const nomeDigitado = document.getElementById("inputNomeCliente").value;
    const telDigitado = document.getElementById("inputTelCliente").value;
    
    localStorage.setItem("saas_nome_cliente", nomeDigitado);
    localStorage.setItem("saas_tel_cliente", telDigitado);
    
    const hiddenDevice = document.getElementById("hiddenDeviceId");
    if (hiddenDevice) {
        hiddenDevice.value = saasDeviceId;
    }
});