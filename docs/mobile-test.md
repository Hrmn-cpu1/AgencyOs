# Abrir no celular pela mesma rede Wi-Fi

Este é um **teste temporário**, com o notebook ligado. Não cria um site na internet. Use somente dados fictícios: a conexão de teste usa HTTP dentro da rede local.

## No notebook Windows

1. Baixe o repositório AgencyOs como ZIP no GitHub e extraia a pasta.
2. Abra o Terminal ou PowerShell na pasta extraída, onde está o arquivo `README.md`. Verifique `python --version` (Python 3.12).
3. Configure um usuário para o banco de teste:

   ```powershell
   python -m agencyos setup --username owner --db data/teste-celular.sqlite3
   ```

   Digite uma senha **nova, usada apenas nesse teste**, com pelo menos 12 caracteres. Ela não aparece enquanto você digita.

4. Ligue o servidor:

   ```powershell
   python -m agencyos serve --lan-test --db data/teste-celular.sqlite3
   ```

5. Se o Windows perguntar sobre acesso pela rede, permita **somente redes privadas**. Mantenha o terminal aberto. A tela mostrará um endereço parecido com `http://192.168.1.25:8000`. Caso não mostre, digite `ipconfig` em outra janela do Terminal e procure o **Endereço IPv4** do Wi-Fi.

## No celular

1. Conecte o celular ao **mesmo Wi-Fi** do notebook. Desligue a VPN e, se necessário, os dados móveis durante o teste.
2. Abra no navegador do celular o endereço exibido no terminal, incluindo `http://` e `:8000`. Exemplo: `http://192.168.1.25:8000` (o número real do seu notebook será diferente).
3. Entre com `owner` e a senha de teste. Use o [roteiro funcional](testing.md) para criar registros fictícios.

Para parar, volte ao terminal do notebook e pressione `Ctrl+C`. O acesso deixa de funcionar quando o notebook, o servidor ou o Wi-Fi são desligados. Não abra a porta no roteador. Se o navegador não abrir, confira se ambos estão no mesmo Wi-Fi, se o endereço IPv4 está correto e se o firewall do Windows permitiu a rede privada.

Para usar fora do Wi-Fi, com o notebook desligado, será necessário hospedar a aplicação com HTTPS e armazenamento persistente em uma nuvem configurada para esse projeto.
