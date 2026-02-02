<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>forward_action</title>
<style>
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;/*최소 화면 높이*/
    display: flex;
    align-items: center; /*세로 가운데*/
    justify-content: center;
    color: white;
}

h2 {
    text-align: center;
    font-size: 2rem;
}
</style>
</head>
<body>
<h2>forward_action.jsp</h2>
	
	<%
	request.setCharacterEncoding("utf-8");
	%>
	
<jsp:forward page="page_control_end.jsp">
<jsp:param name ="phone" value="010=123123"/>
</jsp:forward>

</body>
</html>